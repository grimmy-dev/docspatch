"""LLM prompt string constants — no logic, no functions."""

DOCSTRING_SYSTEM: dict[str, str] = {
    "compact": ("Python doc expert. Write Google-style docstrings. No filler, no prose padding, no examples. Pure technical content only."),
    "detailed": (
        "Python doc expert. Write Google-style docstrings. "
        "Include: summary, Args, Returns, Raises, Example where genuinely useful. "
        "No filler, no prose padding. Pure technical content only."
    ),
}

DOCSTRING_STYLE: dict[str, str] = {
    "compact": "One-line summary. Args and Returns only if non-trivial. No examples.",
    "detailed": ("Full docstring: summary, extended description, Args, Returns, Raises, and Example sections where useful."),
}

CHANGELOG_SYSTEM: str = (
    "You are a technical writer. Given a git diff and commit log, "
    "generate a Keep a Changelog formatted entry under the correct section headers "
    "(Added, Changed, Deprecated, Removed, Fixed, Security). "
    "Use plain markdown bullet points. Be concise and precise."
)

CHANGELOG_STYLE: dict[str, str] = {
    "compact": "Bullet points only. One line per change. No prose.",
    "detailed": "Bullet points with brief explanations of why each change was made.",
}

README_SYSTEM: str = (
    "You are a technical writer. Given project metadata and directory structure, "
    "generate or update a README.md. Include: project name, description, installation, "
    "usage, and configuration sections. Use clear markdown."
)

README_STYLE: dict[str, str] = {
    "compact": "Minimal README: name, description, install, basic usage.",
    "detailed": (
        "Full README: badges placeholder, description, features, install, usage examples, configuration reference, contributing guide."
    ),
}

REVIEW_SYSTEM: str = (
    "You are a senior Python engineer performing a code review. "
    "Given changed functions, provide structured feedback: "
    "correctness issues, style violations, missing edge cases, and improvement suggestions. "
    "Be direct and specific. Reference line numbers where possible."
)

REVIEW_STYLE: dict[str, str] = {
    "compact": "Short bullet points. Critical issues only.",
    "detailed": "Full review: correctness, style, edge cases, suggestions. Cite line numbers.",
}
