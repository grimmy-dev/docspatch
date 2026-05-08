"""Pure prompt-building for the readme pipeline."""

import re
from pathlib import Path

from src.schemas.readme_state import ReadmeState
from src.utils.project.format import MAX_README_CHARS, detect_badges
from src.utils.readme.analysis import build_targeted_readme_context, extract_readme_headings

__all__ = ["README_STYLE", "README_SYSTEM", "build_readme_prompt"]

README_SYSTEM: str = (
    "You are an expert technical writer and software architect. "
    "Generate or update a README.md using only the project context provided in the user message. "
    "Use clear, idiomatic Markdown. Never invent information not present in the context.\n\n"
    "SCOPE RULE — determined by the 'Scope' line in the user message:\n\n"
    "If Scope is 'Project Root':\n"
    "  Write a standard user-facing README.\n"
    "  Include: project name/description, installation, quickstart, CLI usage, configuration, license.\n"
    "  Include badges only if explicitly listed in the context.\n\n"
    "If Scope is a subpackage path (anything other than 'Project Root'):\n"
    "  Write a DEVELOPER-FACING INTERNAL module README.\n"
    "  Include: module purpose, architecture, component responsibilities, public API, internal usage examples.\n"
    "  ABSOLUTELY FORBIDDEN — do not include any of the following:\n"
    "    - Installation instructions of any kind (pip install, uv add, conda, poetry, etc.)\n"
    "    - Setup or onboarding steps\n"
    "    - Badges (PyPI, shields.io, GitHub Actions, coverage, etc.)\n"
    "    - Any URL you were not explicitly given in the context\n"
    "    - License section\n"
    "    - Contributing guide\n"
    "    - Changelog or release history\n"
    "    - Global CLI commands or top-level entry points\n"
    "    - Fabricated links to documentation, issues, or external resources\n"
    "  The reader is an internal developer with the project already installed.\n\n"
    "SECTION UPDATE RULE (when 'Existing README' is provided):\n"
    "  If 'Changed files' are listed → update ONLY sections affected by those files; copy all others verbatim.\n"
    "  If no changed files are listed → rewrite the entire README.\n\n"
    "OUTPUT: Return only the final Markdown. No preamble, no explanations, no surrounding code fences."
)

README_STYLE: dict[str, str] = {
    "compact": "Minimal README. Root: name, description, install, basic usage. Subpackage: module overview and core responsibilities.",
    "detailed": (
        "Full README. Root: badges, description, features, install, usage, config. "
        "Subpackage: architectural breakdown, deep API usage, and internal design notes."
    ),
}


def _compute_scope(state: ReadmeState) -> tuple[bool, str]:
    """Return (is_scoped, scope_label) without mutating state."""
    if state.repo_root and state.target_path:
        target_resolved = Path(state.target_path).resolve()
        repo_resolved = state.repo_root.resolve()
        if target_resolved != repo_resolved:
            try:
                rel = target_resolved.relative_to(repo_resolved)
                return True, str(rel)
            except ValueError:
                return True, str(state.target_path)
    return False, "Project Root"


def build_readme_prompt(state: ReadmeState) -> str:
    """Assemble the LLM user prompt from collected project context.

    Sections ordered stable → dynamic so that a prompt cache prefix covers
    the most-reused content at the front.
    """
    is_scoped, scope_label = _compute_scope(state)
    lines: list[str] = []

    # 1. Aggregated context — most stable (produced by scout + aggregator nodes)
    if state.aggregated_context:
        lines.append(f"Module understanding:\n{state.aggregated_context}\n")

    # 2–3. Project metadata + dependencies (stable)
    ctx = state.project_context
    if ctx.name:
        lines.append(f"Project: {ctx.name}")
    if ctx.version:
        lines.append(f"Version: {ctx.version}")
    if ctx.description:
        lines.append(f"Description: {ctx.description}")
    if state.remote_url:
        lines.append(f"Repository: {state.remote_url}")
    if ctx.dependencies:
        dep_names = [re.split(r"[><=!;@ \[]", d)[0] for d in ctx.dependencies[:20]]
        lines.append(f"Dependencies: {', '.join(dep_names)}")
    if ctx.cli_scripts:
        scripts = ", ".join(f"{k} = {v}" for k, v in ctx.cli_scripts.items())
        lines.append(f"CLI scripts: {scripts}")
    if state.init_docstring:
        lines.append(f"\nModule docstring:\n{state.init_docstring}")

    # 4–5. Dir tree / public API (change occasionally)
    if state.dir_tree:
        lines.append(f"\nDirectory structure:\n{state.dir_tree}")
    if not state.aggregated_context and state.public_api:
        module_cap = 20 if state.style == "compact" else 40
        symbol_cap = 8 if state.style == "compact" else 15
        api_lines = [f"  {mod}: {', '.join(syms[:symbol_cap])}" for mod, syms in list(state.public_api.items())[:module_cap]]
        lines.append("\nPublic API:\n" + "\n".join(api_lines))

    # 6. Usage examples (change occasionally)
    if state.usage_examples:
        cap = 8 if state.style == "compact" else 20
        lines.append("\nUsage examples (from tests):")
        for ex in state.usage_examples[:cap]:
            entry = f"  {ex['fn_name']}: {ex['call']}"
            if ex["context"]:
                entry += f"  # {ex['context']}"
            lines.append(entry)

    # 7. Badges (detailed only, stable but verbose)
    if state.style == "detailed":
        badges = detect_badges(state.remote_url, ctx.name or None, ctx.version, ctx.license_id)
        if badges:
            lines.append("\nInclude these badges near the top:\n" + "\n".join(badges))
        else:
            lines.append("\nDo not include any badges — none could be verified for this project.")

    # 8. Git signals / test coverage (dynamic per run)
    if state.git_signals is not None:
        sig = state.git_signals
        status = "dormant" if sig.is_dormant else "active"
        lines.append(f"\nGit signals: Commits: {sig.commit_count} · First: {sig.first_commit} · Last: {sig.last_commit} · Status: {status}")
    if state.test_coverage:
        lines.append(f"\n{state.test_coverage}")

    # 9. Existing README (dynamic per run)
    if state.existing_readme and not state.rewrite:
        if state.diff_changed_files:
            targeted = build_targeted_readme_context(state.existing_readme, state.diff_changed_files)
            if targeted != state.existing_readme:
                lines.append(f"\nExisting README (targeted):\n{targeted}")
            else:
                headings = extract_readme_headings(state.existing_readme)
                lines.append("\nChanged files:\n" + "\n".join(f"  {f}" for f in state.diff_changed_files))
                if headings:
                    lines.append("Existing sections: " + ", ".join(headings))
                lines.append("Update only sections affected by the changed files. Preserve unaffected sections verbatim.")
                if state.readme_was_truncated:
                    lines.append(
                        f"\nNote: Existing README was truncated to {MAX_README_CHARS} chars for context — "
                        "it continues beyond what is shown. Your output must be a complete, coherent README."
                    )
                if "<!-- dp-keep -->" in state.existing_readme:
                    lines.append(
                        "\nNote: Sections marked <!-- dp-keep -->...<!-- /dp-keep --> will be restored after generation. "
                        "Do not reproduce or modify their content."
                    )
                lines.append(f"\nExisting README:\n{state.existing_readme}")
        else:
            if state.readme_was_truncated:
                lines.append(
                    f"\nNote: Existing README was truncated to {MAX_README_CHARS} chars for context — "
                    "it continues beyond what is shown. Your output must be a complete, coherent README."
                )
            if "<!-- dp-keep -->" in state.existing_readme:
                lines.append(
                    "\nNote: Sections marked <!-- dp-keep -->...<!-- /dp-keep --> will be restored after generation. "
                    "Do not reproduce or modify their content."
                )
            lines.append(f"\nExisting README:\n{state.existing_readme}")
    else:
        lines.append("\nGenerate a fresh README from scratch.")

    # 10. Style, scope, user remarks — dynamic tail
    style_note = README_STYLE.get(state.style, README_STYLE["compact"])
    lines.append(f"\nStyle: {style_note}")
    lines.append(f"Scope: {scope_label}")
    if state.remarks:
        lines.append(f"\nUser instructions (follow exactly):\n{state.remarks}")

    if is_scoped:
        lines.append(
            "\n[REMINDER] This is a MODULE README for internal developers. "
            "Do NOT include: installation, setup, badges, license, contributing, changelog, "
            "or any URL not explicitly provided above. Do not fabricate links."
        )

    return "\n".join(lines)
