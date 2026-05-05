"""Docstring pipeline orchestration."""

import time
from typing import Any, cast

import typer
from langgraph.types import Command
from rich.status import Status

from src.cli.runners._common import iv_type
from src.cli.stream import RetryState, handle_stream_error, stream_graph
from src.cli.ui_handlers import (
    handle_file_pick_interrupt,
    handle_size_check_interrupt,
    run_review_session,
)
from src.schemas.graph_io import CompiledDocpatchGraph, FilePickInterrupt, GraphConfig, SizeCheckInterrupt
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.llm import is_cancelled, reset_cancel
from src.utils.log import get_logger
from src.utils.ui import console, error, info, step, warn

__all__ = ["run_check", "run_docstring"]

logger = get_logger(__name__)

NODE_MESSAGES: dict[str, str] = {
    "scanner": "Scanned repository for Python files",
    "libcst_parser": "Parsed with LibCST and extracted functions",
    "function_hash_check": "Identified significant code changes",
    "batcher": "Batched functions for LLM processing",
    "collect_batches": "Docstring generation complete",
    "writer": "Applied docstrings to source files",
    "cache_update": "Updated local hash cache",
}


async def _stream_until_interrupt(
    graph: CompiledDocpatchGraph,
    payload: DocpatchState | Command[Any] | None,
    config: GraphConfig,
    status: Status,
    is_dry_run: bool = False,
) -> tuple[bool, Any]:
    """Stream docstring pipeline events, tracking batch progress."""
    generation_started = False
    total_batches = 0
    completed_batches = 0

    def on_node(node_name: str, node_data: Any) -> bool:
        nonlocal generation_started, total_batches, completed_batches
        if node_name == "batcher":
            batches = node_data.get("batches", [])
            if batches:
                generation_started = True
                total_batches = len(batches)
                status.update("[dim]Generating docstrings…[/dim]")
            return True
        if node_name == "docwriter_single":
            completed_batches += 1
            if total_batches > 0:
                status.update(f"[dim]Generating docstrings ({completed_batches}/{total_batches})…[/dim]")
            return True
        if node_name == "collect_batches" and not generation_started:
            return True
        return False

    dry_skip = frozenset({"batcher", "collect_batches", "writer", "cache_update"}) if is_dry_run else frozenset()
    return await stream_graph(graph, payload, config, status, NODE_MESSAGES, dry_skip, on_node)


async def run_docstring(graph: CompiledDocpatchGraph, state: DocpatchState, config: GraphConfig) -> None:
    """Async orchestration of the docstring pipeline."""
    from src.utils.validation import validate_state

    try:
        validate_state(state)
    except ValueError as e:
        error(f"State validation failed: {e}")
        raise typer.Exit(code=1) from None

    if not state.dry_run:
        try:
            from src.utils._llm_providers import get_llm

            get_llm(load().defaults.model)
        except RuntimeError as exc:
            error(f"Preflight failed: {exc}")
            raise typer.Exit(1) from exc

    reset_cancel()
    payload: DocpatchState | Command[Any] | None = state
    rs = RetryState()
    start = time.monotonic()

    if not state.dry_run:
        info("Ctrl+C to stop.")

    with console.status("[dim]Initializing pipeline…[/dim]", spinner="dots") as status:
        while True:
            try:
                interrupted, interrupt_val = await _stream_until_interrupt(graph, payload, config, status=status, is_dry_run=state.dry_run)
            except (Exception, KeyboardInterrupt) as exc:
                await handle_stream_error(exc, rs, status)
                payload = None
                status.start()
                continue
            else:
                rs.network_retries = 0

            if not interrupted or interrupt_val is None:
                break

            status.stop()
            kind = iv_type(interrupt_val)

            if kind == "size_check":
                strategy = await handle_size_check_interrupt(cast(SizeCheckInterrupt, interrupt_val))
                if strategy == "quit":
                    info("Aborted.")
                    raise typer.Exit(0)
                payload = Command(resume=strategy)

            elif kind == "file_pick":
                files = cast(FilePickInterrupt, interrupt_val).get("files", [])
                chosen = await handle_file_pick_interrupt(files)
                payload = Command(resume=chosen)

            elif kind == "review":
                current_state = await graph.aget_state(config)
                catalog = current_state.values.get("catalog", {})
                docs = interrupt_val.get("docs", {})
                result = await run_review_session(docs, catalog)
                payload = Command(resume=result)

            else:
                break

            if is_cancelled():
                break

            status.start()

    final_state_data = await graph.aget_state(config)
    final_state = DocpatchState.model_validate(final_state_data.values)

    if final_state.dry_run and final_state.significant_functions:
        from src.cli.display import print_dry_run_breakdown

        print_dry_run_breakdown(final_state)
    elif not final_state.significant_functions:
        info("No undocumented or changed functions found.")

    for w in final_state.warnings:
        warn(w)

    elapsed = time.monotonic() - start
    console.print()
    step(f"Done — {final_state.token_actual:,} tokens used · {elapsed:.1f}s")


def run_check(state: DocpatchState) -> None:
    """Run pipeline to significance only; exit 1 if any functions need documentation."""
    from src.graph.nodes.docstring.hash_check import file_hash_check, function_hash_check
    from src.graph.nodes.docstring.libcst_parser import libcst_parser
    from src.graph.nodes.docstring.scanner import scanner
    from src.graph.nodes.docstring.significance import significance

    step("Scanning")
    state = state.model_copy(update=scanner(state))
    state = state.model_copy(update=file_hash_check(state))
    step("Parsing")
    state = state.model_copy(update=libcst_parser(state))
    state = state.model_copy(update=function_hash_check(state))
    state = state.model_copy(update=significance(state))

    from src.cli.display import print_check_results

    if not state.significant_functions:
        info("All functions documented and up to date.")
        raise typer.Exit(0)

    print_check_results(state.significant_functions, state.catalog)
    raise typer.Exit(1)
