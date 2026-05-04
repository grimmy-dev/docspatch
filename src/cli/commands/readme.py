"""readme command — README generation pipeline."""

import asyncio
from pathlib import Path

import typer

from src.cli.commands._common import command_preamble
from src.schemas.graph_io import GraphConfig
from src.utils.config import load
from src.utils.ui import cli_error_handler

__all__ = ["readme"]


@cli_error_handler
def readme(
    path: Path = typer.Argument(Path("."), help="Repository or target directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show context summary and token estimate without calling LLM"),
    rewrite: bool = typer.Option(False, "--rewrite", help="Regenerate from scratch even if a README already exists"),
    output: Path | None = typer.Option(None, "--output", help="Write README to this path (default: README.md in target dir)"),
    style: str | None = typer.Option(None, "--style", help="compact (minimal) or detailed (badges, full sections). Default from config."),
    remarks: str | None = typer.Option(None, "--remarks", help="Extra instructions passed to LLM (e.g. 'add a development section')"),
) -> None:
    """Generate or update README.md for the repository."""
    command_preamble(path=path, dry_run=dry_run)
    asyncio.run(_readme_async(path, dry_run, rewrite, output, style, remarks))


async def _readme_async(
    path: Path,
    dry_run: bool,
    rewrite: bool,
    output: Path | None,
    style: str | None,
    remarks: str | None,
) -> None:
    """Run the README generation pipeline."""
    from src.cli.runner import run_readme
    from src.graph.graphs.readme_graph import build
    from src.schemas.readme_state import ReadmeState

    cfg = load()
    resolved = Path(path).resolve()
    state = ReadmeState(
        repo_path=resolved,
        target_path=resolved,
        dry_run=dry_run,
        rewrite=rewrite,
        output_path=output.resolve() if output else None,
        style=style or cfg.defaults.style,
        remarks=remarks or "",
    )

    config: GraphConfig = {"configurable": {"thread_id": "readme"}}
    graph = build()
    await run_readme(graph, state, config)
