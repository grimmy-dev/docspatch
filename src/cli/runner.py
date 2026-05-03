"""Pipeline orchestration — thread management and per-pipeline run logic."""

import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import typer
from langgraph.types import Command
from rich.status import Status

from src.cli.display import print_check_results, print_dry_run_breakdown, print_readme_dry_run
from src.cli.stream import RetryState, handle_stream_error, stream_graph
from src.cli.ui_handlers import (
    handle_file_pick_interrupt,
    handle_readme_review_interrupt,
    handle_size_check_interrupt,
    offer_readme_context_view,
    run_review_session,
)
from src.schemas.graph_io import CompiledDocpatchGraph, GraphConfig, SizeCheckInterrupt
from src.schemas.readme_state import CompiledReadmeGraph, ReadmeState
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.git import get_root
from src.utils.llm import is_cancelled, reset_cancel
from src.utils.log import get_logger
from src.utils.ui import console, error, info, step, warn

logger = get_logger(__name__)


def _iv_type(iv: Any) -> str | None:
    return iv.get("type") if isinstance(iv, dict) else None


NODE_MESSAGES: dict[str, str] = {
    "scanner": "Scanned repository for Python files",
    "libcst_parser": "Parsed with LibCST and extracted functions",
    "function_hash_check": "Identified significant code changes",
    "batcher": "Batched functions for LLM processing",
    "collect_batches": "Docstring generation complete",
    "writer": "Applied docstrings to source files",
    "cache_update": "Updated local hash cache",
}

README_NODE_MESSAGES: dict[str, str] = {
    "readme_context": "Collected project context",
    "readme_diff_filter": "Checked for changes",
    "readme_llm": "Generated README content",
    "readme_writer": "Wrote README to disk",
}


def thread_id(command: str, target_path: Path) -> str:
    """16-char hex hash of repo_root + command + path; stable across resumes.

    Args:
        command: The command string.
        target_path: The path associated with the command.

    Returns:
        A 16-character hexadecimal string representing the thread ID."""
    root = get_root()
    key = f"{root}{command}{target_path}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def make_thread(command: str, target_path: Path, resume: bool) -> str:
    """Full thread ID: base_id when resuming, base_id_timestamp for new runs.

    Args:
        command: The command string.
        target_path: The path associated with the command.
        resume: Boolean indicating whether to resume an existing thread.

    Returns:
        A string representing the full thread ID."""
    base = thread_id(command, target_path)
    if resume:
        return base
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{base}_{ts}"


async def stream_until_interrupt(
    graph: CompiledDocpatchGraph,
    payload: DocpatchState | Command[Any] | None,
    config: GraphConfig,
    status: Status,
    is_dry_run: bool = False,
) -> tuple[bool, Any]:
    """Stream docstring pipeline events, tracking batch progress.

    Args:
        graph: The compiled docpatch graph to stream.
        payload: The initial payload for the graph stream.
        config: The graph configuration.
        status: The status display object.
        is_dry_run: If true, skip writing-related nodes.

    Returns:
        A tuple indicating if an interrupt occurred and the interrupt value."""
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
    """Async orchestration of docstring pipeline.

    Args:
        graph: The compiled docpatch graph.
        state: The current docpatch state.
        config: The graph configuration."""
    from src.utils.validation import validate_state

    try:
        validate_state(state)
    except ValueError as e:
        error(f"State validation failed: {e}")
        raise typer.Exit(code=1) from None

    if not state.dry_run:
        try:
            from src.utils.llm import get_llm

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
                interrupted, iv = await stream_until_interrupt(graph, payload, config, status=status, is_dry_run=state.dry_run)
            except (Exception, KeyboardInterrupt) as exc:
                await handle_stream_error(exc, rs, status)
                payload = None  # replay from last checkpoint
                status.start()
                continue
            else:
                rs.network_retries = 0

            if not interrupted or iv is None:
                break

            status.stop()
            iv_type = _iv_type(iv)

            if iv_type == "size_check":
                strategy = await handle_size_check_interrupt(cast(SizeCheckInterrupt, iv))
                if strategy == "quit":
                    info("Aborted.")
                    raise typer.Exit(0)
                payload = Command(resume=strategy)

            elif iv_type == "file_pick":
                chosen = await handle_file_pick_interrupt(iv.get("files", []))
                payload = Command(resume=chosen)

            elif iv_type == "review":
                current_state = await graph.aget_state(config)
                catalog = current_state.values.get("catalog", {})
                docs = iv.get("docs", {})

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
        print_dry_run_breakdown(final_state)
    elif not final_state.significant_functions:
        info("No undocumented or changed functions found.")

    if final_state.warnings:
        for w in final_state.warnings:
            warn(w)

    elapsed = time.monotonic() - start
    console.print()
    step(f"Done — {final_state.token_actual:,} tokens used · {elapsed:.1f}s")


async def run_readme(graph: CompiledReadmeGraph, state: ReadmeState, config: GraphConfig) -> None:
    """Async orchestration of the readme pipeline.

    Args:
        graph: The compiled readme graph.
        state: The current readme state.
        config: The graph configuration."""
    if not state.dry_run:
        try:
            from src.utils.llm import get_llm

            get_llm(load().defaults.review_model)
        except RuntimeError as exc:
            error(f"Preflight failed: {exc}")
            raise typer.Exit(1) from exc

    reset_cancel()
    payload: ReadmeState | Command[Any] | None = state
    rs = RetryState()
    start = time.monotonic()

    if not state.dry_run:
        info("Ctrl+C to stop.")

    dry_skip = frozenset({"readme_llm", "readme_writer"}) if state.dry_run else frozenset()

    with console.status("[dim]Initializing readme pipeline…[/dim]", spinner="dots") as status:
        while True:
            try:
                interrupted, iv = await stream_graph(graph, payload, config, status, README_NODE_MESSAGES, dry_skip)
            except (Exception, KeyboardInterrupt) as exc:
                await handle_stream_error(exc, rs, status)
                payload = None  # replay from last checkpoint
                status.start()
                continue
            else:
                rs.network_retries = 0

            if not interrupted or iv is None:
                break

            status.stop()
            iv_type = _iv_type(iv)

            if iv_type == "readme_review":
                content = iv.get("content", "")
                accepted = await handle_readme_review_interrupt(content, style=state.style)
                if accepted is None:
                    break
                payload = Command(resume=accepted)
            else:
                break

            if is_cancelled():
                break

            status.start()

    final_state_data = await graph.aget_state(config)
    final_state = ReadmeState.model_validate(final_state_data.values)

    if final_state.up_to_date:
        info("README is up to date.")
        return

    if final_state.dry_run:
        from src.graph.nodes.readme.generate import build_readme_prompt

        prompt = build_readme_prompt(final_state)
        print_readme_dry_run(final_state, prompt)
        await offer_readme_context_view(prompt)
    else:
        for w in final_state.warnings:
            warn(w)
        if final_state.accepted_readme is None:
            warn("README not written.")
        else:
            output = final_state.resolved_output_path
            elapsed = time.monotonic() - start
            console.print()
            step(f"README written → {output} — {final_state.token_actual:,} tokens · {elapsed:.1f}s")


def run_check(state: DocpatchState) -> None:
    """Run pipeline to significance only; report and exit 1 if any functions need documentation.

    Args:
        state: The current docpatch state."""
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

    if not state.significant_functions:
        info("All functions documented and up to date.")
        raise typer.Exit(0)

    print_check_results(state.significant_functions, state.catalog)
    raise typer.Exit(1)
