"""clg_llm node — generates changelog entry via LLM."""

from src.schemas.changelog_io import ChangelogLLMUpdate
from src.schemas.changelog_state import ChangelogState
from src.utils.config import load
from src.utils.llm import acall_llm, is_cancelled
from src.utils.log import get_logger
from src.utils.prompts import CHANGELOG_STYLE, CHANGELOG_SYSTEM

__all__ = ["build_clg_prompt", "clg_llm"]

logger = get_logger(__name__)


def build_clg_prompt(state: ChangelogState) -> str:
    """Assemble the LLM user prompt from collected changelog context."""
    style_note = CHANGELOG_STYLE.get(state.style, CHANGELOG_STYLE["compact"])
    lines: list[str] = [f"Style: {style_note}", ""]

    if state.project_name:
        lines.append(f"Project: {state.project_name}")
    if state.project_description:
        lines.append(f"Description: {state.project_description}")
    lines.append(f"Version: {state.version}")

    if state.from_ref:
        end = state.to_ref or "HEAD"
        lines.append(f"Range: {state.from_ref}..{end}")
    else:
        lines.append("Range: uncommitted working tree changes")

    if state.commits:
        lines.append("\nCommits:")
        for commit in state.commits:
            lines.append(f"  - {commit}")

    if state.has_breaking_changes:
        lines.append("\n[INSTRUCTION] This release contains breaking changes. Add a 'Breaking Changes' section before all other sections.")

    if state.is_initial_commit:
        lines.append("\n[INSTRUCTION] This is an initial release. Write an 'Initial Release' overview describing the project.")

    if state.diff:
        label = "Project context" if state.is_initial_commit else "Diff"
        lines.append(f"\n{label}:\n{state.diff}")

    return "\n".join(lines)


async def clg_llm(state: ChangelogState) -> ChangelogLLMUpdate:
    """Call the LLM to generate a changelog entry. Skips on dry_run or nothing_to_document."""
    if is_cancelled() or state.dry_run or state.nothing_to_document:
        return {"generated_entry": "", "token_actual": 0}

    cfg = load()
    _, raw_text, tokens = await acall_llm(
        cfg.defaults.review_model,
        CHANGELOG_SYSTEM,
        build_clg_prompt(state),
        max_tokens=cfg.defaults.changelog_tokens,
    )
    logger.debug("clg_llm: %d tokens, %d chars output", tokens, len(raw_text))
    return {"generated_entry": raw_text, "token_actual": tokens}
