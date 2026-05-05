"""README pipeline orchestration."""

import time
from typing import Any

import typer
from langgraph.types import Command

from src.cli.runners._common import iv_type
from src.cli.stream import RetryState, handle_stream_error, stream_graph
from src.cli.ui_handlers import handle_readme_review_interrupt, offer_readme_context_view
from src.schemas.graph_io import GraphConfig
from src.schemas.readme_state import CompiledReadmeGraph, ReadmeState
from src.utils.config import load
from src.utils.llm import is_cancelled, reset_cancel
from src.utils.log import get_logger
from src.utils.ui import console, error, info, step, warn

__all__ = ["run_readme"]

logger = get_logger(__name__)

README_NODE_MESSAGES: dict[str, str] = {
    "readme_context": "Collected project context",
    "readme_diff_filter": "Checked for changes",
    "readme_llm": "Generated README content",
    "readme_writer": "Wrote README to disk",
}


async def run_readme(graph: CompiledReadmeGraph, state: ReadmeState, config: GraphConfig) -> None:
    """Async orchestration of the README pipeline."""
    if not state.dry_run:
        try:
            from src.utils._llm_providers import get_llm

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
                interrupted, interrupt_val = await stream_graph(graph, payload, config, status, README_NODE_MESSAGES, dry_skip)
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

            if kind == "readme_review":
                content = interrupt_val.get("content", "")
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

        from src.cli.display import print_readme_dry_run

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
