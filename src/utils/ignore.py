"""Respect .docsignore files using pathspec gitignore matching."""

from pathlib import Path

import pathspec

from src.utils.log import get_logger

logger = get_logger(__name__)

DEFAULT_IGNORE_PATTERNS = [
    "tests/",
    "**/tests/",
    "__init__.py",
    "**/__init__.py",
]


def load_ignore(root: Path) -> pathspec.PathSpec[pathspec.Pattern]:
    """Build an ignore spec from built-in defaults and optional .docsignore at the repository root.

    Args:
        root: The root directory of the repository.

    Returns:
        A PathSpec combining default patterns and any user-defined patterns. This spec is always returned,
        even if .docsignore is absent."""
    patterns = list(DEFAULT_IGNORE_PATTERNS)

    ignore_file = root / ".docsignore"
    if ignore_file.exists():
        try:
            user_lines = ignore_file.read_text().splitlines()
            patterns.extend(line for line in user_lines if line.strip() and not line.startswith("#"))
            logger.debug("load_ignore: loaded %d user patterns from .docsignore", len(user_lines))
        except OSError as exc:
            logger.debug("Could not read .docsignore: %s", exc)

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def is_ignored(spec: pathspec.PathSpec[pathspec.Pattern], root: Path, abs_path: Path) -> bool:
    """Return True if the absolute path matches the ignore spec relative to the provided root.

    Args:
        spec: The PathSpec object containing ignore patterns.
        root: The root directory from which the relative path of `abs_path` is calculated.
        abs_path: The absolute path of the file to check against the ignore patterns.

    Returns:
        True if `abs_path` should be ignored; False otherwise, including if `abs_path` is not
        a descendant of `root`."""
    try:
        rel = abs_path.relative_to(root)
        return bool(spec.match_file(str(rel)))
    except ValueError:
        return False
