"""Changelog pipeline orchestration."""

from typing import Any

from langgraph.types import Command

from src.cli.runners.pipeline import run_pipeline
from src.cli.ui_handlers import handle_clg_review_interrupt, offer_context_view
from src.schemas.changelog_state import ChangelogState, CompiledChangelogGraph
from src.schemas.graph_io import GraphConfig
from src.utils.config import load
from src.utils.log import get_logger
from src.utils.ui import console, info, step, warn

__all__ = ["run_clg"]

logger = get_logger(__name__)

CLG_NODE_MESSAGES: dict[str, str] = {
    "clg_context": "Collected git context",
    "clg_llm": "Generated changelog entry",
    "clg_writer": "Wrote changelog to disk",
}


async def run_clg(graph: CompiledChangelogGraph, state: ChangelogState, config: GraphConfig) -> None:
    """Async orchestration of the changelog pipeline."""
    preflight_model = None if state.dry_run else load().defaults.review_model
    dry_skip = frozenset({"clg_llm", "clg_writer"}) if state.dry_run else frozenset()

    async def clg_review_handler(iv: Any) -> Command[Any] | None:
        content = iv.get("content", "")
        accepted = await handle_clg_review_interrupt(content)
        if accepted is None:
            return None
        return Command(resume=accepted)

    elapsed = await run_pipeline(
        graph,
        state,
        config,
        node_messages=CLG_NODE_MESSAGES,
        dry_skip=dry_skip,
        init_message="Initializing changelog pipeline…",
        preflight_model=preflight_model,
        interrupt_handlers={"clg_review": clg_review_handler},
    )

    final_state_data = await graph.aget_state(config)
    final_state = ChangelogState.model_validate(final_state_data.values)

    if final_state.nothing_to_document:
        info("Nothing to document — no diff or commits found.")
        return

    if final_state.dry_run:
        from src.cli.display import print_clg_dry_run
        from src.graph.nodes.changelog.prompts import build_clg_prompt
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
            console.print()
            step(f"Changelog written → {output} — {final_state.token_actual:,} tokens · {elapsed:.1f}s")
