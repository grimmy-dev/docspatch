"""Unified git reader — single seam for all pipeline git queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import git

from src.utils.git.changelog import (
    get_commit_log,
    get_git_diff,
    get_initial_commit_context,
    is_initial_commit,
)
from src.utils.git.repo import get_repo
from src.utils.log import get_logger

__all__ = ["GitReader", "GitSignals"]


@dataclass
class GitSignals:
    """Structured git activity data — commit count, date range, and dormancy flag."""

    commit_count: int
    first_commit: str  # "YYYY-MM"
    last_commit: str  # "YYYY-MM"
    is_dormant: bool  # True when last commit > 12 months ago


logger = get_logger(__name__)


class GitReader:
    """Read-only git interface for pipeline nodes.

    Wraps all gitpython calls behind a single seam — one import, one mock in tests.
    Instantiate once from state.repo_path at the start of each pipeline node.
    """

    def __init__(self, path: Path | None = None) -> None:
        """Open the repository at path (or cwd); raise RuntimeError when not found."""
        self._repo: git.Repo = get_repo(path)
        self._root = Path(str(self._repo.working_tree_dir))

    @property
    def root(self) -> Path:
        """Working-tree root of the repository."""
        return self._root

    def resolve_target(self, path: Path | None) -> Path:
        """Resolve a nullable target path against repo root.

        Returns path.resolve() when given, or root when None.
        Prevents relative CLI inputs from escaping the repository boundary.
        """
        return Path(path).resolve() if path is not None else self._root

    # --- File listing (docstring pipeline) ---

    def list_committed_files(self, target: Path, from_ref: str | None) -> list[str]:
        """Return relative paths of committed files under target.

        With from_ref: files in the from_ref..HEAD range.
        Without from_ref: all cached (tracked) files.
        """
        try:
            if from_ref:
                raw: str = self._repo.git.diff("--name-only", from_ref, "HEAD", "--", str(target))
                return raw.splitlines()
            cached: str = self._repo.git.ls_files("--cached", str(target))
            return cached.splitlines()
        except Exception as exc:  # noqa: BLE001
            logger.debug("list_committed_files failed: %s", exc)
            return []

    def list_untracked_files(self, target: Path) -> list[str]:
        """Return relative paths of untracked files under target."""
        try:
            others: str = self._repo.git.ls_files("--others", "--exclude-standard", str(target))
            return others.splitlines()
        except Exception as exc:  # noqa: BLE001
            logger.debug("list_untracked_files failed: %s", exc)
            return []

    # --- Diff operations (readme + changelog pipelines) ---

    def get_diff(self, from_ref: str | None, to_ref: str | None) -> str:
        """Return filtered unified diff with noise pathspecs applied."""
        return get_git_diff(self._repo, from_ref, to_ref)

    def get_raw_diff(self, target: Path | None = None) -> str:
        """Return raw HEAD diff, optionally scoped to target path."""
        try:
            args: list[str] = ["HEAD", "--"]
            if target is not None:
                args.append(str(target))
            result: str = self._repo.git.diff(*args)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.debug("get_raw_diff failed: %s", exc)
            return ""

    def get_diff_files(self, target: Path) -> list[str]:
        """Return Python files under target that differ from HEAD."""
        try:
            output = self._repo.git.diff("HEAD", "--name-only", "--", str(target))
            return [f for f in output.strip().splitlines() if f.endswith(".py")]
        except Exception as exc:  # noqa: BLE001
            logger.debug("get_diff_files failed: %s", exc)
            return []

    # --- Commit history (changelog pipeline) ---

    def get_commit_log(self, from_ref: str | None, to_ref: str | None) -> list[str]:
        """Return commit log as 'shorthash subject' strings."""
        return get_commit_log(self._repo, from_ref, to_ref)

    def is_initial_commit(self) -> bool:
        """Return True when the repo has exactly one commit."""
        return is_initial_commit(self._repo)

    def get_initial_commit_context(self) -> str:
        """Return README + file list for an initial-release changelog entry."""
        return get_initial_commit_context(self._repo, self._root)

    # --- Activity signals (readme pipeline) ---

    def get_remote_url(self) -> str | None:
        """Return the first remote URL, or None when no remotes exist."""
        try:
            return self._repo.remotes[0].url if self._repo.remotes else None
        except (IndexError, AttributeError) as exc:
            logger.debug("get_remote_url failed: %s", exc)
            return None

    def get_activity_signals(self) -> GitSignals | None:
        """Return structured git activity data, or None on any failure."""
        try:
            count = int(self._repo.git.rev_list("--count", "HEAD").strip())
            last = self._repo.git.log("-1", "--format=%ci", "HEAD").strip()[:7]
            first = self._repo.git.log("--reverse", "-1", "--format=%ci", "HEAD").strip()[:7]
            last_dt = datetime.strptime(last, "%Y-%m")
            now = datetime.now()
            months_since = (now.year - last_dt.year) * 12 + (now.month - last_dt.month)
            return GitSignals(
                commit_count=count,
                first_commit=first,
                last_commit=last,
                is_dormant=months_since > 12,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("get_activity_signals failed: %s", exc)
            return None
