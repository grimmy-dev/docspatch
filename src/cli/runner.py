"""Pipeline orchestration helpers — thread ID, streaming, and execution."""

import asyncio
import hashlib
import time
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import typer
from langgraph.types import Command
from rich.status import Status

from src.cli.ui_handlers import (
    handle_file_pick_interrupt,
    handle_size_check_interrupt,
    interactive_model_switch,
    print_check_results,
    print_dry_run_breakdown,
    run_review_session,
)
from src.schemas.graph_io import CompiledDocpatchGraph, GraphConfig, SizeCheckInterrupt
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.errors import NetworkError, RateLimitError, classify_llm_error
from src.utils.git import get_root
from src.utils.llm import is_cancelled, request_cancel, reset_cancel
from src.utils.log import get_logger
from src.utils.ui import console, error, info, step, warn

logger = get_logger(__name__)

MAX_RATE_LIMIT_RETRIES = 10
MAX_NETWORK_RETRIES = 5
NETWORK_RETRY_BASE_DELAY = 5

NODE_MESSAGES = {
    "scanner": "Scanned repository for Python files",
    "libcst_parser": "Parsed with LibCST and extracted functions",
    "function_hash_check": "Identified significant code changes",
    "batcher": "Batched functions for LLM processing",
    "collect_batches": "Docstring generation complete",
    "writer": "Applied docstrings to source files",
    "cache_update": "Updated local hash cache",
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
    """Streams data until an interrupt is received."""
    generation_started = False
    total_batches = 0
    completed_batches = 0

    async for event in graph.astream(payload, config, stream_mode="updates"):
        if "__interrupt__" in event:
            return True, event["__interrupt__"][0].value if event["__interrupt__"] else None

        for node_name, node_data in event.items():
            if is_dry_run and node_name in [
                "batcher",
                "collect_batches",
                "writer",
                "cache_update",
            ]:
                continue

            if node_name == "batcher":
                batches = node_data.get("batches", [])
                if batches:
                    generation_started = True
                    total_batches = len(batches)
                    status.update(f"[dim]Generating docstrings (Batch 0/{total_batches})...[/dim]")

            elif node_name == "docwriter_single":
                completed_batches += 1
                if total_batches > 0:
                    status.update(f"[dim]Generating docstrings (Batch {completed_batches}/{total_batches})...[/dim]")

            elif node_name in NODE_MESSAGES:
                if node_name == "collect_batches" and not generation_started:
                    continue

                status.stop()
                step(NODE_MESSAGES[node_name])
                status.start()

    return False, None


async def run(graph: CompiledDocpatchGraph, state: DocpatchState, config: GraphConfig) -> None:
    """Async orchestration of a full pipeline run."""
    from src.utils.validation import validate_state

    try:
        validate_state(state)
    except ValueError as e:
        error(msg=f"State Validation Failed: {e}")
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
    retries = 0
    network_retries = 0
    start = time.monotonic()

    if not state.dry_run:
        info(msg="Ctrl+C to stop.")

    with console.status("[dim]Initializing pipeline...\n[/dim]", spinner="dots") as status:
        while True:
            try:
                interrupted, iv = await stream_until_interrupt(graph, payload, config, status=status, is_dry_run=state.dry_run)
            except RateLimitError:
                status.stop()
                action = await interactive_model_switch()
                if action == "abort":
                    raise typer.Exit(1) from None
                if action == "wait":
                    retries += 1
                    if retries > MAX_RATE_LIMIT_RETRIES:
                        warn(f"Rate limit retries exhausted after {MAX_RATE_LIMIT_RETRIES} attempts.")
                        raise typer.Exit(1) from None
                    delay = min(60 * (2 ** (retries - 1)), 120)
                    console.print(f"[yellow]Waiting {delay}s before retry {retries}/{MAX_RATE_LIMIT_RETRIES}…[/yellow]")
                    await asyncio.sleep(delay)
                payload = Command(resume=None)
                status.start()
                continue
            except NetworkError:
                status.stop()
                network_retries += 1
                if network_retries > MAX_NETWORK_RETRIES:
                    warn(f"Server unreachable after {MAX_NETWORK_RETRIES} attempts.")
                    raise typer.Exit(1) from None
                delay = min(NETWORK_RETRY_BASE_DELAY * (2 ** (network_retries - 1)), 60)
                console.print(f"[yellow]Server not responding. Retry {network_retries}/{MAX_NETWORK_RETRIES} in {delay}s…[/yellow]")
                await asyncio.sleep(delay)
                payload = Command(resume=None)
                status.start()
                continue
            except KeyboardInterrupt:
                status.stop()
                request_cancel()
                raise SystemExit(130) from None
            except Exception as exc:
                status.stop()
                raise classify_llm_error(exc) from None
            else:
                network_retries = 0

            if not interrupted or iv is None:
                break

            status.stop()
            iv_type = iv.get("type") if isinstance(iv, dict) else None

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
    console.print(f"""\n[green]✓[/green] Done — {final_state.token_actual:,} tokens used · Took: {elapsed:.1f}s""")


def run_check(state: DocpatchState) -> None:
    """Run pipeline to significance only; report and exit 1 if any functions need documentation."""
    from src.graph.nodes.hash_check import file_hash_check, function_hash_check
    from src.graph.nodes.libcst_parser import libcst_parser
    from src.graph.nodes.scanner import scanner
    from src.graph.nodes.significance import significance

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
