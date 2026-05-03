"""Git repository helpers."""

from pathlib import Path

import git

from src.utils.log import get_logger

logger = get_logger(__name__)


def get_repo(path: Path | None = None) -> git.Repo:
    """Return the git.Repo for the given path (or cwd); search parent dirs.

    Raises RuntimeError when no git repository is found."""
    try:
        return git.Repo(path or ".", search_parent_directories=True)
    except git.InvalidGitRepositoryError as exc:
        raise RuntimeError("Not a git repository.") from exc


def is_git_repo(path: Path | None = None) -> bool:
    """Return True when path (or cwd) is inside a git repository."""
    try:
        get_repo(path)
        return True
    except RuntimeError:
        return False


def get_root(repo: git.Repo | None = None) -> Path:
    """Return the working-tree root of the repository."""
    r = repo or get_repo()
    return Path(str(r.working_tree_dir))
