"""Shared pre-flight helpers used by multiple commands."""

from pathlib import Path

import typer

from src.utils.config import get_api_key
from src.utils.git.repo import is_git_repo

__all__ = ["command_preamble"]


def command_preamble(path: Path | None = None, dry_run: bool = False) -> None:
    """Validate environment and credentials before command execution.

    Raises typer.BadParameter when not in a git repo or no API key is set."""
    if not is_git_repo(path):
        raise typer.BadParameter("Not a git repository. Run dp from inside a git repo.")
    if not dry_run and get_api_key() is None:
        raise typer.BadParameter("No API key configured. Run `dp setup` first.")
