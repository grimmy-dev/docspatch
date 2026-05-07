"""Context signals for README generation — git history, test coverage, diff detection."""

from __future__ import annotations

import ast
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.log import get_logger

if TYPE_CHECKING:
    import git

logger = get_logger(__name__)

__all__ = [
    "build_targeted_readme_context",
    "extract_readme_headings",
    "get_diff_files",
    "get_git_signals",
    "get_test_coverage_summary",
    "map_files_to_sections",
    "parse_readme_sections",
]


def get_git_signals(repo: git.Repo) -> str:
    """Return a compact git history and activity summary. Empty string on any failure."""
    try:
        count = int(repo.git.rev_list("--count", "HEAD").strip())
        last = repo.git.log("-1", "--format=%ci", "HEAD").strip()[:7]
        first = repo.git.log("--reverse", "-1", "--format=%ci", "HEAD").strip()[:7]
        last_dt = datetime.strptime(last, "%Y-%m")
        now = datetime.now()
        months_since = (now.year - last_dt.year) * 12 + (now.month - last_dt.month)
        status = "dormant" if months_since > 12 else "active"
        return f"Commits: {count} · First: {first} · Last: {last} · Status: {status}"
    except Exception as exc:  # noqa: BLE001 — git may be absent or repo malformed
        logger.debug("get_git_signals failed: %s", exc)
        return ""


_TEST_NAMES_PER_MODULE = 6


def get_test_coverage_summary(root: Path) -> str:
    """Return test function names grouped by module as plain-english behaviour signals.

    Caps at _TEST_NAMES_PER_MODULE names per module. Uses rglob to find nested test dirs.
    Empty string when no tests found."""
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return ""
    modules: dict[str, list[str]] = {}
    for test_file in sorted(tests_dir.rglob("test_*.py")):
        try:
            tree = ast.parse(test_file.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as _:
            continue
        names = [
            node.name.removeprefix("test_").replace("_", " ")
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        ]
        if names:
            module_name = test_file.stem.removeprefix("test_").replace("_", " ").title()
            modules[module_name] = names[:_TEST_NAMES_PER_MODULE]
    if not modules:
        return ""
    parts = "; ".join(f"{mod}: {', '.join(names)}" for mod, names in modules.items())
    return f"Tests — {parts}"


def get_diff_files(repo: git.Repo, target: Path) -> list[str]:
    """Return Python files under target that differ from HEAD. Empty list on failure."""
    try:
        output = repo.git.diff("HEAD", "--name-only", "--", str(target))
        return [f for f in output.strip().splitlines() if f.endswith(".py")]
    except Exception as exc:  # noqa: BLE001
        logger.debug("get_diff_files failed: %s", exc)
        return []


def extract_readme_headings(readme: str) -> list[str]:
    """Return ## and ### level heading text from a Markdown README. Pure."""
    return [re.sub(r"^#+\s*", "", line).strip() for line in readme.splitlines() if re.match(r"^#{2,3}\s", line)]


_STOP_WORDS: frozenset[str] = frozenset({"the", "and", "in", "a", "of", "for", "to", "is", "it", "or", "on", "at", "as", "by"})

_SECTION_SPLIT_RE = re.compile(r"(?=^## )", re.MULTILINE)
_PATH_TOKEN_RE = re.compile(r"[/_\-.]")


def _tokenize(text: str) -> set[str]:
    """Split text on path/word separators into lowercase non-stop-word tokens."""
    raw = re.split(r"[/_\-.\s]+", text.lower())
    return {t for t in raw if t and t not in _STOP_WORDS}


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


_TARGETING_FOOTER = "[INSTRUCTION] Copy all [KEEP] sections verbatim into your output. Update only [UPDATE] sections."


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
