"""Stub commands — not yet implemented."""

from pathlib import Path

import typer

from src.utils.ui import info

__all__ = ["init", "review"]


def review(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    since: str | None = typer.Option(None, "--since", help="Git ref to compare against"),
) -> None:
    """Review generated documentation."""
    del path, since
    info("coming soon")


def init(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Initialize a new repository."""
    del path, dry_run
    info("coming soon")
