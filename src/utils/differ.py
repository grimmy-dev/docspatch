"""Pure functions for detecting meaningful code changes.

Core layer — no I/O, no side effects.
"""

import re

from src.schemas.function import FunctionMetadata

# Full-line comments only — avoids corrupting URLs inside strings
COMMENT_RE = re.compile(r"(?m)^\s*#.*$")
TRIPLE_DOUBLE_RE = re.compile(r'""".*?"""', re.DOTALL)
TRIPLE_SINGLE_RE = re.compile(r"'''.*?'''", re.DOTALL)
WHITESPACE_RE = re.compile(r"\s+")


def normalize(source: str) -> str:
    """Strip comments and docstrings then collapse whitespace.

    Produces a canonical form for body-hash comparison so that
    doc-only or comment-only edits do not trigger regeneration.
    """
    s = COMMENT_RE.sub("", source)
    s = TRIPLE_DOUBLE_RE.sub("", s)
    s = TRIPLE_SINGLE_RE.sub("", s)
    return WHITESPACE_RE.sub(" ", s).strip()


def is_significant(old_body: str, new_body: str) -> bool:
    """Return True when normalised bodies differ (logic changed)."""
    return normalize(old_body) != normalize(new_body)


def has_meaningful_changes(functions: list[FunctionMetadata]) -> bool:
    """Return True when at least one function is marked significant."""
    return any(f.is_significant for f in functions)
