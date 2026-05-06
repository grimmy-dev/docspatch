"""Shell-layer git operations for the changelog pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.log import get_logger

if TYPE_CHECKING:
    import git

__all__ = ["get_commit_log", "get_git_diff", "get_initial_commit_context", "is_initial_commit"]

logger = get_logger(__name__)

_NOISE_PATHSPECS: tuple[str, ...] = (
    ":(exclude)*.lock",
    ":(exclude)*-lock.json",
    ":(exclude)*.min.js",
    ":(exclude)*.min.css",
    ":(exclude)dist/",
    ":(exclude)build/",
    ":(exclude)**/*.pyc",
    ":(exclude)**/*_pb2.py",
)


def _decode(msg: str | bytes | bytearray) -> str:
    """Decode commit message to str without calling bytes() on an existing str."""
    if isinstance(msg, str):
        return msg
    return msg.decode("utf-8", errors="replace")


def get_git_diff(repo: git.Repo, from_ref: str | None, to_ref: str | None) -> str:
    """Return filtered unified diff as a string.

    Without from_ref: diffs working tree against HEAD.
    With from_ref: diffs from_ref..to_ref (to_ref defaults to HEAD).
    Lockfiles, minified, and generated files excluded via git pathspecs."""
    try:
        if from_ref is None:
            result: str = repo.git.diff("HEAD", "--", *_NOISE_PATHSPECS)
        else:
            end = to_ref or "HEAD"
            result = repo.git.diff(f"{from_ref}..{end}", "--", *_NOISE_PATHSPECS)
        return result
    except Exception as exc:  # noqa: BLE001 — git may be absent or ref invalid
        logger.debug("get_git_diff failed: %s", exc)
        return ""


def get_commit_log(repo: git.Repo, from_ref: str | None, to_ref: str | None) -> list[str]:
    """Return commit log as 'shorthash subject' strings.

    Without from_ref: returns empty — working tree changes have no commits.
    With from_ref: returns commits in from_ref..to_ref range."""
    if from_ref is None:
        return []
    try:
        end = to_ref or "HEAD"
        raw = repo.git.log(f"{from_ref}..{end}", "--format=%h %s")
        return [_decode(line) for line in raw.strip().splitlines() if line.strip()]
    except Exception as exc:  # noqa: BLE001
        logger.debug("get_commit_log failed: %s", exc)
        return []


def is_initial_commit(repo: git.Repo) -> bool:
    """Return True when the repo has exactly one commit."""
    try:
        return int(repo.git.rev_list("--count", "HEAD").strip()) == 1
    except Exception as exc:  # noqa: BLE001
        logger.debug("is_initial_commit failed: %s", exc)
        return False


def get_initial_commit_context(repo: git.Repo, root: Path) -> str:
    """Return README + file list as context for an initial-release changelog entry.

    Substitutes for the diff when there is no meaningful diff to document."""
    parts: list[str] = []
    readme = root / "README.md"
    if readme.exists():
        try:
            parts.append(f"README:\n{readme.read_text(encoding='utf-8')[:3000]}")
        except OSError:
            pass
    try:
        parts.append(f"Files:\n{repo.git.ls_files()}")
    except Exception as exc:  # noqa: BLE001
        logger.debug("get_initial_commit_context: ls_files failed: %s", exc)
    return "\n\n".join(parts)
