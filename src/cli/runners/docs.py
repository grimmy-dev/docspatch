"""Docstring pipeline orchestration."""

from typing import Any, cast

import typer
from langgraph.types import Command
from rich.status import Status

from src.cli.runners.pipeline import run_pipeline
from src.cli.ui_handlers import (
    handle_file_pick_interrupt,
    handle_size_check_interrupt,
    run_review_session,
)
from src.schemas.graph_io import CompiledDocpatchGraph, FilePickInterrupt, GraphConfig, SizeCheckInterrupt
from src.schemas.state import DocpatchState
from src.utils.config import load
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


async def run_docstring(graph: CompiledDocpatchGraph, state: DocpatchState, config: GraphConfig) -> None:
    """Async orchestration of the docstring pipeline."""
    from src.utils.validation import validate_state

    try:
        validate_state(state)
    except ValueError as e:
        error(f"State validation failed: {e}")
        raise typer.Exit(code=1) from None

    preflight_model = None if state.dry_run else load().defaults.model
    dry_skip = frozenset({"batcher", "collect_batches", "writer", "cache_update"}) if state.dry_run else frozenset()

    generation_started = False
    total_batches = 0
    completed_batches = 0

    def on_node(node_name: str, node_data: Any, status: Status) -> bool:
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

    async def size_check_handler(iv: Any) -> Command[Any] | None:
        strategy = await handle_size_check_interrupt(cast(SizeCheckInterrupt, iv))
        if strategy == "quit":
            info("Aborted.")
            raise typer.Exit(0)
        return Command(resume=strategy)

    async def file_pick_handler(iv: Any) -> Command[Any] | None:
        files = cast(FilePickInterrupt, iv).get("files", [])
        chosen = await handle_file_pick_interrupt(files)
        return Command(resume=chosen)

    async def review_handler(iv: Any) -> Command[Any] | None:
        current_state = await graph.aget_state(config)
        catalog = current_state.values.get("catalog", {})
        docs = iv.get("docs", {})
        result = await run_review_session(docs, catalog)
        return Command(resume=result)

    elapsed = await run_pipeline(
        graph,
        state,
        config,
        node_messages=NODE_MESSAGES,
        dry_skip=dry_skip,
        init_message="Initializing pipeline…",
        preflight_model=preflight_model,
        interrupt_handlers={
            "size_check": size_check_handler,
            "file_pick": file_pick_handler,
            "review": review_handler,
        },
        on_node=on_node,
    )

    final_state_data = await graph.aget_state(config)
    final_state = DocpatchState.model_validate(final_state_data.values)

    if final_state.dry_run and final_state.significant_functions:
        from src.cli.display import print_dry_run_breakdown

        print_dry_run_breakdown(final_state)
    elif not final_state.significant_functions:
        info("No undocumented or changed functions found.")

    for w in final_state.warnings:
        warn(w)

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
