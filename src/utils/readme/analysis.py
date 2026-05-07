"""Pure README analysis — section parsing, heading extraction, and targeted context."""

from __future__ import annotations

import re

__all__ = [
    "build_targeted_readme_context",
    "extract_readme_headings",
    "map_files_to_sections",
    "parse_readme_sections",
]

_STOP_WORDS: frozenset[str] = frozenset({"the", "and", "in", "a", "of", "for", "to", "is", "it", "or", "on", "at", "as", "by"})

_SECTION_SPLIT_RE = re.compile(r"(?=^## )", re.MULTILINE)
_PATH_TOKEN_RE = re.compile(r"[/_\-.]")

_TARGETING_FOOTER = "[INSTRUCTION] Copy all [KEEP] sections verbatim into your output. Update only [UPDATE] sections."


def _tokenize(text: str) -> set[str]:
    """Split text on path/word separators into lowercase non-stop-word tokens."""
    raw = re.split(r"[/_\-.\s]+", text.lower())
    return {t for t in raw if t and t not in _STOP_WORDS}


def extract_readme_headings(readme: str) -> list[str]:
    """Return ## and ### level heading text from a Markdown README. Pure."""
    return [re.sub(r"^#+\s*", "", line).strip() for line in readme.splitlines() if re.match(r"^#{2,3}\s", line)]


def parse_readme_sections(readme: str) -> list[tuple[str, str]]:
    """Split README into (heading, content) pairs by H2 boundaries.

    Preamble content before the first ## becomes ('__preamble__', text).
    Each subsequent chunk retains its heading line plus all body lines.
    """
    chunks = _SECTION_SPLIT_RE.split(readme)
    sections: list[tuple[str, str]] = []
    for chunk in chunks:
        if not chunk.strip():
            continue
        first_line = chunk.splitlines()[0]
        if first_line.startswith("## "):
            heading = first_line.lstrip("# ").strip()
            sections.append((heading, chunk))
        else:
            sections.append(("__preamble__", chunk))
    return sections


def map_files_to_sections(changed_files: list[str], headings: list[str]) -> set[str]:
    """Return headings likely affected by changed_files based on token overlap.

    Uses prefix matching so file tokens like 'install' match heading tokens like
    'installation'. Returns empty set when nothing matches, signalling the caller
    to fall back to the full README.
    """
    file_tokens = [_tokenize(f) for f in changed_files]
    matched: set[str] = set()
    for heading in headings:
        heading_tokens = _tokenize(heading)
        for ft in file_tokens:
            if any(
                ht == ft_tok or ht.startswith(ft_tok) or ft_tok.startswith(ht)
                for ht in heading_tokens
                for ft_tok in ft
            ):
                matched.add(heading)
                break
    return matched


def build_targeted_readme_context(readme: str, changed_files: list[str]) -> str:
    """Return targeted README context: full content for affected sections, heading-only for unaffected.

    Falls back to the original readme string when no section matches any changed
    file, letting the caller detect this by comparing against the original.
    """
    if not readme or not changed_files:
        return readme

    sections = parse_readme_sections(readme)
    non_preamble_headings = [h for h, _ in sections if h != "__preamble__"]
    affected = map_files_to_sections(changed_files, non_preamble_headings)

    if not affected:
        return readme

    parts: list[str] = []
    for heading, content in sections:
        if heading == "__preamble__":
            parts.append(content)
        elif heading in affected:
            parts.append(f"[UPDATE] {content}")
        else:
            heading_line = content.splitlines()[0]
            parts.append(f"[KEEP] {heading_line}")

    parts.append(_TARGETING_FOOTER)
    return "\n".join(parts)
