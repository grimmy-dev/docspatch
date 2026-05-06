"""Pure semantic diff filtering for the changelog pipeline.

Core layer — no I/O, no side effects. Fully testable without mocking."""

from __future__ import annotations

import fnmatch
import re
from typing import TypedDict

__all__ = ["FilteredDiff", "estimate_diff_signal_ratio", "filter_diff_noise", "score_and_filter_commits"]

_SIGNATURE_RE = re.compile(r"^[+-](async def |def |class )\w")
_NOISE_FILE_GLOBS = ("*.lock", "*.pyc", "*.min.js", "*.min.css")
_NOISE_PATH_PARTS = ("__pycache__/",)
_IMPORT_RE = re.compile(r"^[+-]\s*(import |from \S+ import )")
_TOML_VERSION_RE = re.compile(r'^[+-]\s*version\s*=\s*"')
_CONVENTIONAL_TYPE_RE = re.compile(r"^[a-f0-9]+ ([a-zA-Z]+)(\([^)]+\))?([!])?: ")
_DROP_TYPES = frozenset({"chore", "style", "refactor", "test", "docs", "ci", "build", "bump", "release"})
_LOGIC_RE = re.compile(r"^(async def |def |class |if |for |while |return |yield |raise |with |assert |\w+ =)")


class FilteredDiff(TypedDict):
    """Result of filter_diff_noise — filtered content plus drop statistics."""

    content: str
    dropped_hunks: int
    drop_reasons: list[str]


def _is_noise_file(path: str) -> bool:
    """Return True if path matches known generated/noise file patterns."""
    if any(part in path for part in _NOISE_PATH_PARTS):
        return True
    return any(fnmatch.fnmatch(path, pat) for pat in _NOISE_FILE_GLOBS)


def _changed_lines(hunk_body: str) -> list[str]:
    """Extract +/- lines from a hunk body, excluding --- and +++ header lines."""
    return [line for line in hunk_body.splitlines() if line.startswith(("+", "-")) and not line.startswith(("---", "+++"))]


def _has_signature(changed: list[str]) -> bool:
    """Return True if any changed line touches a function/class signature."""
    return any(_SIGNATURE_RE.match(line) for line in changed)


def _is_whitespace_only(changed: list[str]) -> bool:
    """Return True if all changed lines are blank or whitespace-only."""
    return bool(changed) and all(line[1:].strip() == "" for line in changed)


def _is_comment_only(changed: list[str]) -> bool:
    """Return True if all changed lines are Python single-line comments."""
    return bool(changed) and all(line[1:].lstrip().startswith("#") for line in changed)


def _is_import_reorder(changed: list[str]) -> bool:
    """Return True if added and removed lines are the same set of import statements."""
    added = {line[1:].strip() for line in changed if line.startswith("+") and _IMPORT_RE.match(line)}
    removed = {line[1:].strip() for line in changed if line.startswith("-") and _IMPORT_RE.match(line)}
    if not added or not removed:
        return False
    non_import = [line for line in changed if not _IMPORT_RE.match(line)]
    return added == removed and not non_import


def _is_docstring_only(changed: list[str]) -> bool:
    """Heuristic: all changed content is docstring text — triple-quoted, no code constructs."""
    stripped = [line[1:].strip() for line in changed]
    has_marker = any('"""' in s or "'''" in s for s in stripped)
    has_code = any(re.match(r"(def |class |async def |import |from |\w+ =|return |if |for )", s) for s in stripped if s)
    return has_marker and not has_code


def _is_toml_version_only(changed: list[str]) -> bool:
    """Return True if all changed lines in a .toml hunk are version assignments."""
    return bool(changed) and all(_TOML_VERSION_RE.match(line) for line in changed)


def _drop_reason(file_path: str, changed: list[str]) -> str | None:
    """Return drop reason string, or None if the hunk should be kept."""
    if _has_signature(changed):
        return None
    if _is_noise_file(file_path):
        return "noise-file"
    if not changed:
        return "empty-hunk"
    if _is_whitespace_only(changed):
        return "whitespace-only"
    if _is_comment_only(changed):
        return "comment-only"
    if _is_import_reorder(changed):
        return "import-reorder"
    if _is_docstring_only(changed):
        return "docstring-only"
    if file_path.endswith(".toml") and _is_toml_version_only(changed):
        return "toml-version-bump"
    return None


def _parse_file_path(section_header: str) -> str:
    """Extract b/ file path from 'diff --git a/... b/...' line."""
    m = re.search(r" b/(.+)", section_header.split("\n", 1)[0])
    return m.group(1) if m else ""


def _parse_hunks(section: str) -> tuple[str, list[tuple[str, str]]]:
    """Split a file section into file header and (hunk_header, hunk_body) pairs."""
    parts = re.split(r"(\n@@ [^\n]+)", section)
    file_header = parts[0]
    hunks: list[tuple[str, str]] = []
    i = 1
    while i < len(parts) - 1:
        hunks.append((parts[i], parts[i + 1]))
        i += 2
    return file_header, hunks


def filter_diff_noise(raw_diff: str) -> FilteredDiff:
    """Strip noise hunks from a unified diff, returning only signal content."""
    if not raw_diff.strip():
        return {"content": raw_diff, "dropped_hunks": 0, "drop_reasons": []}

    sections = re.split(r"(?=\ndiff --git )", raw_diff)
    kept_parts: list[str] = []
    dropped_hunks = 0
    drop_reasons: list[str] = []

    for section in sections:
        if not section.strip():
            continue
        file_path = _parse_file_path(section)
        file_header, hunks = _parse_hunks(section)
        if not hunks:
            kept_parts.append(section)
            continue
        kept_hunks: list[str] = []
        for hunk_header, hunk_body in hunks:
            changed = _changed_lines(hunk_body)
            reason = _drop_reason(file_path, changed)
            if reason is None:
                kept_hunks.append(hunk_header + hunk_body)
            else:
                dropped_hunks += 1
                if reason not in drop_reasons:
                    drop_reasons.append(reason)
        if kept_hunks:
            kept_parts.append(file_header + "".join(kept_hunks))

    return {"content": "".join(kept_parts), "dropped_hunks": dropped_hunks, "drop_reasons": drop_reasons}


def score_and_filter_commits(commits: list[str]) -> list[str]:
    """Filter commit list to keep only user-facing changes (feat/fix/perf/breaking/free-form)."""
    if not commits:
        return commits
    kept: list[str] = []
    for commit in commits:
        msg = commit.split(" ", 1)[1] if " " in commit else commit
        m = _CONVENTIONAL_TYPE_RE.match(commit)
        if not m:
            kept.append(commit)
            continue
        ctype, _, bang = m.group(1), m.group(2), m.group(3)
        is_breaking = bang == "!" or "BREAKING" in msg
        if is_breaking or ctype not in _DROP_TYPES:
            kept.append(commit)
    return kept if kept else list(commits)


def estimate_diff_signal_ratio(raw_diff: str) -> float:
    """Return 0.0–1.0 ratio of signal lines (signatures/logic) to total changed lines."""
    total = 0
    signal = 0
    for line in raw_diff.splitlines():
        if not line.startswith(("+", "-")) or line.startswith(("---", "+++")):
            continue
        total += 1
        content = line[1:].strip()
        if _SIGNATURE_RE.match(line) or _LOGIC_RE.match(content):
            signal += 1
    return signal / total if total > 0 else 0.0
