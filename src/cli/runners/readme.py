"""README pipeline orchestration."""

from typing import Any

from langgraph.types import Command

from src.cli.runners.pipeline import run_pipeline
from src.cli.ui_handlers import handle_readme_review_interrupt, offer_context_view
from src.schemas.graph_io import GraphConfig
from src.schemas.readme_state import CompiledReadmeGraph, ReadmeState
from src.utils.config import load
from src.utils.log import get_logger
from src.utils.ui import console, info, step, warn

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
    preflight_model = None if state.dry_run else load().defaults.review_model
    dry_skip = frozenset({"readme_llm", "readme_writer"}) if state.dry_run else frozenset()

    async def readme_review_handler(iv: Any) -> Command[Any] | None:
        content = iv.get("content", "")
        accepted = await handle_readme_review_interrupt(content, style=state.style)
        if accepted is None:
            return None
        return Command(resume=accepted)

    elapsed = await run_pipeline(
        graph,
        state,
        config,
        node_messages=README_NODE_MESSAGES,
        dry_skip=dry_skip,
        init_message="Initializing readme pipeline…",
        preflight_model=preflight_model,
        interrupt_handlers={"readme_review": readme_review_handler},
    )

    final_state_data = await graph.aget_state(config)
    final_state = ReadmeState.model_validate(final_state_data.values)

    if final_state.up_to_date:
        info("README is up to date.")
        return

    if final_state.dry_run:
        from src.cli.display import print_readme_dry_run
        from src.graph.nodes.readme.prompts import build_readme_prompt
        from src.utils.llm.prompts import README_SYSTEM

        prompt = build_readme_prompt(final_state)
        print_readme_dry_run(final_state, prompt)
        await offer_context_view(f"{README_SYSTEM}\n\n---\n\n{prompt}")
    else:
        for w in final_state.warnings:
            warn(w)
        if final_state.accepted_readme is None:
            warn("README not written.")
        else:
            output = final_state.resolved_output_path
            console.print()
            step(f"README written → {output} — {final_state.token_actual:,} tokens · {elapsed:.1f}s")
