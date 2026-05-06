"""clg command — changelog generation pipeline."""

import asyncio
from pathlib import Path

import typer

from src.cli.commands._common import command_preamble
from src.schemas.graph_io import GraphConfig
from src.utils.config import load
from src.utils.ui import cli_error_handler

__all__ = ["clg"]


@cli_error_handler
def clg(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    from_ref: str | None = typer.Option(
        None, "--from", help="Start ref (tag, commit, branch). Without this, diffs uncommitted working tree changes."
    ),
    to_ref: str | None = typer.Option(None, "--to", help="End ref (default: HEAD). Only used with --from."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be generated without calling LLM"),
    output: Path | None = typer.Option(None, "--output", help="Write changelog to this path (default: CHANGELOG.md in repo root)"),
    style: str | None = typer.Option(None, "--style", help="compact or detailed"),
) -> None:
    """Generate a Keep a Changelog entry from git diff and commit history."""
    command_preamble(path=path, dry_run=dry_run)
    asyncio.run(_clg_async(path, from_ref, to_ref, dry_run, output, style))


async def _clg_async(
    path: Path,
    from_ref: str | None,
    to_ref: str | None,
    dry_run: bool,
    output: Path | None,
    style: str | None,
) -> None:
    """Run the changelog generation pipeline."""
    from src.cli.runners import run_clg
    from src.graph.graphs.clg_graph import build
    from src.schemas.changelog_state import ChangelogState

    cfg = load()
    resolved = Path(path).resolve()
    state = ChangelogState(
        repo_path=resolved,
        from_ref=from_ref,
        to_ref=to_ref,
        dry_run=dry_run,
        output_path=output.resolve() if output else None,
        style=style or cfg.defaults.style,
    )

    config: GraphConfig = {"configurable": {"thread_id": "clg"}}
    graph = build()
    await run_clg(graph, state, config)
