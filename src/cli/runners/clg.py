"""Changelog pipeline orchestration."""

import time
from typing import Any

import typer
from langgraph.types import Command

from src.cli.runners._common import iv_type
from src.cli.stream import RetryState, handle_stream_error, stream_graph
from src.cli.ui_handlers import handle_clg_review_interrupt, offer_context_view
from src.schemas.changelog_state import ChangelogState, CompiledChangelogGraph
from src.schemas.graph_io import GraphConfig
from src.utils.config import load
from src.utils.llm import is_cancelled, reset_cancel
from src.utils.log import get_logger
from src.utils.ui import console, error, info, step, warn

__all__ = ["run_clg"]

logger = get_logger(__name__)

CLG_NODE_MESSAGES: dict[str, str] = {
    "clg_context": "Collected git context",
    "clg_llm": "Generated changelog entry",
    "clg_writer": "Wrote changelog to disk",
}


async def run_clg(graph: CompiledChangelogGraph, state: ChangelogState, config: GraphConfig) -> None:
    """Async orchestration of the changelog pipeline."""
    if not state.dry_run:
        try:
            from src.utils._llm_providers import get_llm

            get_llm(load().defaults.review_model)
        except RuntimeError as exc:
            error(f"Preflight failed: {exc}")
            raise typer.Exit(1) from exc

    reset_cancel()
    payload: ChangelogState | Command[Any] | None = state
    rs = RetryState()
    start = time.monotonic()

    if not state.dry_run:
        info("Ctrl+C to stop.")

    dry_skip = frozenset({"clg_llm", "clg_writer"}) if state.dry_run else frozenset()

    with console.status("[dim]Initializing changelog pipeline…[/dim]", spinner="dots") as status:
        while True:
            try:
                interrupted, interrupt_val = await stream_graph(graph, payload, config, status, CLG_NODE_MESSAGES, dry_skip)
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

            if kind == "clg_review":
                content = interrupt_val.get("content", "")
                accepted = await handle_clg_review_interrupt(content)
                if accepted is None:
                    break
                payload = Command(resume=accepted)
            else:
                break

            if is_cancelled():
                break

            status.start()

    final_state_data = await graph.aget_state(config)
    final_state = ChangelogState.model_validate(final_state_data.values)

    if final_state.nothing_to_document:
        info("Nothing to document — no diff or commits found.")
        return

    if final_state.dry_run:
        from src.cli.display import print_clg_dry_run
        from src.graph.nodes.changelog.generate import build_clg_prompt
        from src.utils.prompts import CHANGELOG_SYSTEM

        prompt = build_clg_prompt(final_state)
        print_clg_dry_run(final_state, prompt)
        await offer_context_view(f"{CHANGELOG_SYSTEM}\n\n---\n\n{prompt}")
    else:
        for w in final_state.warnings:
            warn(w)
        if final_state.accepted_entry is None:
            warn("Changelog entry not written.")
        else:
            output = final_state.resolved_output_path
            elapsed = time.monotonic() - start
            console.print()
            step(f"Changelog written → {output} — {final_state.token_actual:,} tokens · {elapsed:.1f}s")
