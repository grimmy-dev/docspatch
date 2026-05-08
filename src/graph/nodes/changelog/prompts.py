"""Pure prompt-building for the changelog pipeline."""

from src.schemas.changelog_state import ChangelogState

__all__ = ["CHANGELOG_STYLE", "CHANGELOG_SYSTEM", "build_clg_prompt"]

CHANGELOG_SYSTEM: str = (
    "You are a technical writer generating changelog entries for end users, not for developers.\n"
    "Given a git diff and commit log, write a Keep a Changelog entry using these section headers only: "
    "Added, Changed, Deprecated, Removed, Fixed, Security.\n\n"
    "RULES:\n"
    "- Describe user-facing impact, not implementation details.\n"
    "- DO NOT describe line-by-line code changes, variable renames, or internal refactors "
    "unless they directly affect the public API or user behaviour.\n"
    "- Each bullet point is one logical change written from the user's perspective.\n"
    "- Omit sections that have no changes.\n"
    "- Use the project name and description (if provided) to frame changes in terms the user cares about.\n"
    "- If the diff contains only internal refactors with no API or behaviour change visible to users, "
    "write a single 'Changed' bullet noting the internal cleanup — do not expand it.\n"
    "- Begin your output with `## [version] - YYYY-MM-DD` as the first line "
    "(use the Version field provided; use today's date or omit the date if unknown).\n"
    "- OUTPUT: Return only the changelog entry Markdown. No preamble, no code fences."
)

CHANGELOG_STYLE: dict[str, str] = {
    "compact": "Bullet points only. One line per change. No rationale.",
    "detailed": (
        "Bullet points with a brief explanation of why each change was made. "
        "If breaking changes are present, add a '### Breaking Changes' section first."
    ),
}


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
