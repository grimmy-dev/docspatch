"""Generic LangGraph streaming helpers — retry logic and event loop."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import typer
from rich.status import Status

from src.cli.ui_handlers import interactive_model_switch
from src.schemas.graph_io import GraphConfig
from src.utils.errors import NetworkError, RateLimitError, classify_llm_error
from src.utils.llm import request_cancel
from src.utils.ui import step, warn

MAX_RATE_LIMIT_RETRIES = 10
MAX_NETWORK_RETRIES = 5
NETWORK_RETRY_BASE_DELAY = 5


@dataclass
class RetryState:
    retries: int = 0
    network_retries: int = 0


async def stream_graph(
    graph: Any,
    payload: Any,
    config: GraphConfig,
    status: Status,
    node_messages: dict[str, str],
    dry_skip: frozenset[str] = frozenset(),
    on_node: Callable[[str, Any], bool] | None = None,
) -> tuple[bool, Any]:  # (was_interrupted, interrupt_value)
    """Core stream loop shared by all pipelines.

    on_node(name, data) returns True to suppress the default step message."""
    async for event in graph.astream(payload, config, stream_mode="updates"):
        if "__interrupt__" in event:
            return True, event["__interrupt__"][0].value if event["__interrupt__"] else None
        for node_name, node_data in event.items():
            if node_name in dry_skip:
                continue
            suppress = on_node(node_name, node_data) if on_node else False
            if not suppress and node_name in node_messages:
                status.stop()
                step(node_messages[node_name])
                status.start()
    return False, None


async def handle_stream_error(exc: Exception | KeyboardInterrupt, rs: RetryState, status: Status) -> None:
    """Handle a stream exception. Returns normally when the caller should retry; raises otherwise."""
    if isinstance(exc, KeyboardInterrupt):
        status.stop()
        request_cancel()
        raise SystemExit(130) from None
    if isinstance(exc, RateLimitError):
        status.stop()
        action = await interactive_model_switch()
        if action == "abort":
            raise typer.Exit(1) from None
        if action == "wait":
            rs.retries += 1
            if rs.retries > MAX_RATE_LIMIT_RETRIES:
                warn(f"Rate limit retries exhausted after {MAX_RATE_LIMIT_RETRIES} attempts.")
                raise typer.Exit(1) from None
            delay = min(60 * (2 ** (rs.retries - 1)), 120)
            warn(f"Waiting {delay}s before retry {rs.retries}/{MAX_RATE_LIMIT_RETRIES}…")
            await asyncio.sleep(delay)
        return
    if isinstance(exc, NetworkError):
        status.stop()
        rs.network_retries += 1
        if rs.network_retries > MAX_NETWORK_RETRIES:
            warn(f"Server unreachable after {MAX_NETWORK_RETRIES} attempts.")
            raise typer.Exit(1) from None
        delay = min(NETWORK_RETRY_BASE_DELAY * (2 ** (rs.network_retries - 1)), 60)
        warn(f"Server not responding. Retry {rs.network_retries}/{MAX_NETWORK_RETRIES} in {delay}s…")
        await asyncio.sleep(delay)
        return
    status.stop()
    raise classify_llm_error(exc) from exc
