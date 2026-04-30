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
    """Build ignore spec from built-in defaults plus optional .docsignore at repo root.

    Always returns a PathSpec — defaults apply even when .docsignore is absent.
    Users can negate a default with ! (e.g. '!tests/') in their .docsignore.

    Args:
        root: The root directory of the repository.

    Returns:
        A PathSpec combining default patterns and any user-defined patterns.
    """
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
    """Return True when abs_path matches the ignore spec relative to root.

    Args:
        spec: The PathSpec object.
        root: The root directory to calculate the relative path from.
        abs_path: The absolute path of the file to check.

    Returns:
        True if the file should be ignored, False otherwise.
    """
    try:
        rel = abs_path.relative_to(root)
        return bool(spec.match_file(str(rel)))
    except ValueError:
        return False
