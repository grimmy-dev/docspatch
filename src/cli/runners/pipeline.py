"""Generic pipeline runner — owns the retry/interrupt/status loop shared by all pipelines."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

import typer
from langgraph.types import Command
from rich.status import Status

from src.cli.stream import RetryState, handle_stream_error, stream_graph
from src.schemas.graph_io import GraphConfig
from src.utils.llm.caller import is_cancelled, reset_cancel
from src.utils.ui import console, error, info

__all__ = ["run_pipeline"]

InterruptHandler = Callable[[Any], Awaitable[Command[Any] | None]]


async def run_pipeline(
    graph: Any,
    state: Any,
    config: GraphConfig,
    *,
    node_messages: dict[str, str],
    dry_skip: frozenset[str],
    init_message: str,
    preflight_model: str | None,
    interrupt_handlers: dict[str, InterruptHandler],
    on_node: Callable[[str, Any, Status], bool] | None = None,
) -> float:
    """Run a LangGraph pipeline with retry, interrupt dispatch, and cancellation.

    preflight_model=None skips the LLM availability check (dry-run case).
    Returns elapsed seconds; callers handle final state readback and display.
    """
    if preflight_model is not None:
        try:
            from src.utils.llm.factory import get_llm

            get_llm(preflight_model)
        except RuntimeError as exc:
            error(f"Preflight failed: {exc}")
            raise typer.Exit(1) from exc

    reset_cancel()
    payload: Any = state
    rs = RetryState()
    start = time.monotonic()

    if preflight_model is not None:
        info("Ctrl+C to stop.")

    with console.status(f"[dim]{init_message}[/dim]", spinner="dots") as status:
        while True:
            try:
                interrupted, interrupt_val = await stream_graph(
                    graph, payload, config, status, node_messages, dry_skip, on_node
                )
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
            kind = interrupt_val.get("type") if isinstance(interrupt_val, dict) else None
            handler = interrupt_handlers.get(kind) if kind else None

            if handler is None:
                break

            result = await handler(interrupt_val)
            if result is None:
                break
            payload = result

            if is_cancelled():
                break

            status.start()

    return time.monotonic() - start
