"""docs command — docstring generation pipeline."""

import asyncio
from pathlib import Path

import typer

from src.cli.commands._common import command_preamble
from src.schemas.graph_io import GraphConfig
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.ui import cli_error_handler, step

__all__ = ["docs"]


@cli_error_handler
def docs(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Estimate tokens and cost without writing"),
    style: str | None = typer.Option(None, "--style", help="compact (one-liner) or detailed (full docstring). Default from config."),
    since: str | None = typer.Option(None, "--since", help="Only document functions changed since this git ref (e.g. HEAD~3, main)."),
    update: bool = typer.Option(False, "--update", help="Re-document all functions, including already documented ones"),
    resume: bool = typer.Option(False, "--resume", help="Resume a previously interrupted run (uses stable thread ID)"),
    check: bool = typer.Option(False, "--check", help="Exit 1 if any functions need docs — no LLM, safe for CI"),
) -> None:
    """Generate docstrings for functions in a repository."""
    command_preamble(path=path, dry_run=True)
    if check:
        _run_check(path, since, update)
        return
    asyncio.run(_docs_async(path, dry_run, style, since, update, resume))


async def _docs_async(
    path: Path,
    dry_run: bool,
    style: str | None,
    since: str | None,
    update: bool,
    resume: bool,
) -> None:
    """Run the docstring generation pipeline."""
    from src.cli.runners import make_thread, run_docstring
    from src.graph.graphs.docs_graph import build
    from src.utils.checkpointer import get_checkpointer, get_memory_saver

    step("Performing Checks")
    cfg = load()
    resolved = Path(path).resolve()
    state = DocpatchState(
        repo_path=resolved,
        target_path=resolved,
        dry_run=dry_run,
        style=style or cfg.defaults.style,
        from_ref=since,
        update_all=update,
    )

    tid = make_thread("docs", resolved, resume=resume)
    config: GraphConfig = {"configurable": {"thread_id": tid}}

    if dry_run:
        graph = build(checkpointer=get_memory_saver())
        await run_docstring(graph, state, config)
        return

    saver, serde = await get_checkpointer()
    async with saver as checkpointer:
        checkpointer.serde = serde
        graph = build(checkpointer=checkpointer)
        await run_docstring(graph, state, config)


def _run_check(path: Path, since: str | None, update: bool) -> None:
    """Run the CI check — exit 1 if undocumented/changed functions exist."""
    from src.cli.runners import run_check

    resolved = Path(path).resolve()
    cfg = load()
    state = DocpatchState(
        repo_path=resolved,
        target_path=resolved,
        dry_run=True,
        style=cfg.defaults.style,
        from_ref=since,
        update_all=update,
    )
    run_check(state)
