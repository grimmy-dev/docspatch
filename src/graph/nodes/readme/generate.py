"""readme_llm node — generates or updates README content via LLM."""

import re
from pathlib import Path

from src.schemas.readme_io import ReadmeLLMUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.config import load
from src.utils.llm import acall_llm, is_cancelled
from src.utils.log import get_logger
from src.utils.project_format import MAX_README_CHARS, detect_badges
from src.utils.prompts import README_STYLE, README_SYSTEM
from src.utils.readme_signals import extract_readme_headings

logger = get_logger(__name__)


def build_readme_prompt(state: ReadmeState) -> str:
    """Assemble the LLM user prompt from collected project context."""
    style_note = README_STYLE.get(state.style, README_STYLE["compact"])
    lines: list[str] = [f"Style: {style_note}", ""]

    # Explicit scope label — LLM uses this to apply the scope rule from the system prompt
    is_scoped = False
    if state.repo_root and state.target_path:
        target_resolved = Path(state.target_path).resolve()
        repo_resolved = state.repo_root.resolve()
        if target_resolved != repo_resolved:
            is_scoped = True
            try:
                rel = target_resolved.relative_to(repo_resolved)
                lines.append(f"Scope: {rel}")
            except ValueError:
                lines.append(f"Scope: {state.target_path}")
        else:
            lines.append("Scope: Project Root")
    else:
        lines.append("Scope: Project Root")
    lines.append("")

    if state.project_name:
        lines.append(f"Project: {state.project_name}")
    if state.project_version:
        lines.append(f"Version: {state.project_version}")
    if state.project_description:
        lines.append(f"Description: {state.project_description}")
    if state.remote_url:
        lines.append(f"Repository: {state.remote_url}")
    if state.dependencies:
        dep_names = [re.split(r"[><=!;@ \[]", d)[0] for d in state.dependencies[:20]]
        lines.append(f"Dependencies: {', '.join(dep_names)}")
    if state.cli_scripts:
        scripts = ", ".join(f"{k} = {v}" for k, v in state.cli_scripts.items())
        lines.append(f"CLI scripts: {scripts}")
    if state.init_docstring:
        lines.append(f"\nModule docstring:\n{state.init_docstring}")
    if state.dir_tree:
        lines.append(f"\nDirectory structure:\n{state.dir_tree}")

    if state.public_api:
        module_cap = 20 if state.style == "compact" else 40
        symbol_cap = 8 if state.style == "compact" else 15
        api_lines = [f"  {mod}: {', '.join(syms[:symbol_cap])}" for mod, syms in list(state.public_api.items())[:module_cap]]
        lines.append("\nPublic API:\n" + "\n".join(api_lines))

    if state.style == "detailed":
        badges = detect_badges(state.remote_url, state.project_name or None, state.project_version, state.license_id)
        if badges:
            lines.append("\nInclude these badges near the top:\n" + "\n".join(badges))
        else:
            lines.append("\nDo not include any badges — none could be verified for this project.")

    if state.git_signals:
        lines.append(f"\nGit signals: {state.git_signals}")
    if state.test_coverage:
        lines.append(f"\n{state.test_coverage}")

    if state.existing_readme and not state.rewrite:
        if state.diff_changed_files:
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
        lines.append("\nGenerate a fresh README from scratch.")

    if state.remarks:
        lines.append(f"\nUser instructions (follow exactly):\n{state.remarks}")

    if is_scoped:
        lines.append(
            "\n[REMINDER] This is a MODULE README for internal developers. "
            "Do NOT include: installation, setup, badges, license, contributing, changelog, "
            "or any URL not explicitly provided above. Do not fabricate links."
        )

    return "\n".join(lines)


async def readme_llm(state: ReadmeState) -> ReadmeLLMUpdate:
    """Call the LLM to generate or update the README. Skips on dry_run."""
    if is_cancelled() or state.dry_run:
        return {"generated_readme": "", "token_actual": 0}

    cfg = load()
    max_tokens = cfg.defaults.readme_tokens_compact if state.style == "compact" else cfg.defaults.readme_tokens_detailed
    _, raw_text, tokens = await acall_llm(cfg.defaults.review_model, README_SYSTEM, build_readme_prompt(state), max_tokens=max_tokens)

    logger.debug("readme_llm: %d tokens, %d chars output", tokens, len(raw_text))
    return {"generated_readme": raw_text, "token_actual": tokens}
