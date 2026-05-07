"""Pure prompt-building for the changelog pipeline."""

from src.schemas.changelog_state import ChangelogState
from src.utils.llm.prompts import CHANGELOG_STYLE

__all__ = ["build_clg_prompt"]


def build_clg_prompt(state: ChangelogState) -> str:
    """Assemble the LLM user prompt from collected changelog context.

    Stable content (project metadata, version, style) precedes dynamic content
    (commits, diff) so repeated runs share a cacheable prompt prefix.
    """
    style_note = CHANGELOG_STYLE.get(state.style, CHANGELOG_STYLE["compact"])
    lines: list[str] = []

    if state.project_name:
        lines.append(f"Project: {state.project_name}")
    if state.project_description:
        lines.append(f"Description: {state.project_description}")
    lines.append(f"Version: {state.version}")
    lines.append(f"Style: {style_note}")
    lines.append("")

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
