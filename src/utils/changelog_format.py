"""Pure formatting and analysis utilities for the changelog pipeline.

Core layer — no I/O. Fully testable without mocking."""

import re

__all__ = ["detect_breaking_changes", "truncate_diff"]

_CONVENTIONAL_BREAKING_RE = re.compile(r"^[a-z]+(\([^)]+\))?!:")


def truncate_diff(diff: str, cap: int) -> tuple[str, bool]:
    """Truncate diff to cap chars, appending a note. Returns (diff, was_truncated)."""
    if len(diff) <= cap:
        return diff, False
    note = f"\n[Diff truncated — showing {cap:,} of {len(diff):,} chars]"
    return diff[:cap] + note, True


def detect_breaking_changes(commits: list[str], diff: str) -> bool:
    """Return True if any signal indicates a breaking change.

    Checks Conventional Commit markers (! suffix or BREAKING CHANGE footer) first,
    then falls back to scanning for removed top-level public def/class in the diff."""
    for entry in commits:
        msg = entry.split(" ", 1)[1] if " " in entry else entry
        if _CONVENTIONAL_BREAKING_RE.match(msg) or "BREAKING CHANGE" in msg:
            return True
    for line in diff.splitlines():
        if re.match(r"^-(?!-)(def |class )[A-Za-z]", line):
            return True
    return False
