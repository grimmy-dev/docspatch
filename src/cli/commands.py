"""CLI command definitions and async entry points."""

import asyncio
import os
import subprocess
from pathlib import Path

import questionary
import typer
from langgraph.checkpoint.memory import MemorySaver

from src.cli.provider import configure_provider, current_provider_name
from src.schemas.graph_io import GraphConfig
from src.schemas.state import DocpatchState
from src.utils.config import get_api_key, load, save
from src.utils.git import is_git_repo
from src.utils.ui import Q_STYLE, cli_error_handler, console, info, step, warn


def mask_key(key: str | None) -> str:
    """Returns a masked API key for safe display.

    Args:
        key (str | None): The API key to mask.

    Returns:
        str: The masked API key string."""
    if not key:
        return "[dim]not set[/dim]"
    if len(key) <= 8:
        return "[green]●●●●[/green]"
    return f"[green]{key[:4]}...{key[-4:]}[/green]"


def command_preamble(path: Path | None = None, dry_run: bool = False) -> None:
    """Validates the environment and credentials before command execution.

    Args:
        path (Path | None): The repository path.
        dry_run (bool): If True, skips API key validation.

    Returns:
        None: Raises `typer.BadParameter` on validation failure."""
    if not is_git_repo(path):
        raise typer.BadParameter("Not a git repository. Run dp from inside a git repo.")
    if not dry_run and get_api_key() is None:
        raise typer.BadParameter("No API key configured. Run `dp setup` first.")


@cli_error_handler
def docs(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    style: str | None = typer.Option(None, "--style", help="compact or detailed"),
    since: str | None = typer.Option(None, "--since", help="Git ref to diff from"),
    update: bool = typer.Option(False, "--update", help="Re-document all functions"),
    resume: bool = typer.Option(False, "--resume", help="Resume interrupted run"),
    check: bool = typer.Option(False, "--check", help="Exit 1 if undocumented/changed functions exist (no LLM)"),
) -> None:
    """Generates documentation for functions within a repository.

    Args:
        path (Path): Repository path.
        dry_run (bool): Preview without writing.
        style (str | None): Documentation style ('compact' or 'detailed').
        since (str | None): Git ref to diff from.
        update (bool): Re-document all functions.
        resume (bool): Resume interrupted run.
        check (bool): Exit 1 if undocumented/changed functions exist (no LLM).

    Returns:
        None."""
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
    """Executes the asynchronous documentation generation pipeline.

    Args:
        path (Path): The repository path.
        dry_run (bool): If True, performs a preview without writing.
        style (str | None): The documentation style.
        since (str | None): The Git ref to diff from.
        update (bool): If True, re-documents all functions.
        resume (bool): If True, resumes an interrupted run.

    Returns:
        None."""
    from src.cli.runner import make_thread, run
    from src.graph.graphs.docs_graph import build
    from src.utils.checkpointer import get_checkpointer

    step(name="Performing Checks")
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
    saver, serde = await get_checkpointer()

    if dry_run:
        memory_checkpointer = MemorySaver()
        memory_checkpointer.serde = serde
        graph = build(checkpointer=memory_checkpointer)
        await run(graph, state, config)
        return

    async with saver as checkpointer:
        checkpointer.serde = serde
        graph = build(checkpointer=checkpointer)
        await run(graph, state, config)


def _run_check(path: Path, since: str | None, update: bool) -> None:
    """Prepares state and initiates the documentation check.

    Args:
        path (Path): The repository path.
        since (str | None): The Git ref to diff from.
        update (bool): If True, updates all functions.

    Returns:
        None."""
    from src.cli.runner import run_check

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


@cli_error_handler
def setup() -> None:
    """Run interactive setup to configure style and LLM provider."""
    cfg = load()
    style = questionary.select("Docstring style:", choices=["compact", "detailed"], style=Q_STYLE).ask()
    if style is None:
        raise typer.Abort()
    new_defaults = cfg.defaults.model_copy(update={"style": style})
    updated = configure_provider(cfg.model_copy(update={"defaults": new_defaults}))
    if updated:
        save(updated)
        step("Setup complete", current_provider_name(updated))


@cli_error_handler
def config(
    action: str = typer.Argument("show", help="Action: show, set, or edit"),
    key: str | None = typer.Argument(None, help="Config key to set"),
    value: str | None = typer.Argument(None, help="Value for scalar keys"),
) -> None:
    """View or modify configuration settings.

    Args:
        action: Action: show, set, or edit.
        key: Config key to set.
        value: Value for scalar keys."""
    from rich.table import Table

    cfg = load()
    if action == "show":
        settings_table = Table(show_header=False, box=None, padding=(0, 2))
        settings_table.add_column("Key", style="bold")
        settings_table.add_column("Value", style="sandy_brown")
        for k, v in cfg.defaults.model_dump().items():
            settings_table.add_row(k, str(v))

        keys_table = Table(show_header=False, box=None, padding=(0, 2))
        keys_table.add_column("Provider", style="bold")
        keys_table.add_column("Key")
        for provider, key_val in [
            ("Google Gemini", cfg.keys.google_api_key),
            ("OpenAI", cfg.keys.openai_api_key),
            ("Anthropic", cfg.keys.anthropic_api_key),
        ]:
            keys_table.add_row(provider, mask_key(key_val))

        console.print("\n[bold]Settings[/bold]")
        console.print(settings_table)
        console.print("\n[bold]API Keys[/bold]")
        console.print(keys_table)
        console.print("\n[dim]dp config edit — open in editor  ·  dp config set provider — change provider[/dim]")
    elif action == "set":
        if key in ("provider", "model", "review_model"):
            updated = configure_provider(cfg)
            if updated:
                save(updated)
                step("Config updated")
        else:
            warn(f"Unknown key '{key}'. Settable: provider, model, review_model.")
    elif action in ("edit", "open"):
        from src.utils.config import CONFIG_PATH

        if not CONFIG_PATH.exists():
            save(cfg)
        info("Opening config in your editor. Save and close to apply.")

        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if editor:
            subprocess.run([editor, str(CONFIG_PATH)])
        else:
            # macOS: open, Windows: os.startfile, Linux: xdg-open or webbrowser
            typer.launch(str(CONFIG_PATH))
        step("Config saved.")
    else:
        warn(f"Unknown action '{action}'. Valid: show, set, edit.")


@cli_error_handler
def cleanup() -> None:
    """Delete local docspatch data interactively."""
    from src.constants import DOCSPATCH_DIR

    if not DOCSPATCH_DIR.exists():
        info("Nothing to clean up.")
        return

    choices = [
        questionary.Choice("Checkpoints (SQLite DB history)", value="checkpoints.db"),
        questionary.Choice("Cache (File & Function hashes)", value="cache.json"),
        questionary.Choice("Logs", value="docspatch.log"),
        questionary.Choice("Config (API Keys & Settings)", value="config.toml"),
    ]

    selected = questionary.checkbox("Select data to remove (use Space to select):", choices=choices, style=Q_STYLE).ask()

    if not selected:
        info("No items selected. Cleanup cancelled.")
        return

    for item in selected:
        path = DOCSPATCH_DIR / item
        if path.exists():
            path.unlink()
            step(f"Deleted {item}")

    if not any(DOCSPATCH_DIR.iterdir()):
        DOCSPATCH_DIR.rmdir()


def readme(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Generate README.md for the repository.

    Args:
        path: Repository path.
        dry_run: Preview without writing."""
    info("coming soon")


def clg(
    from_ref: str = typer.Option("HEAD~1", "--from", help="Start ref"),
    to_ref: str = typer.Option("HEAD", "--to", help="End ref"),
) -> None:
    """Generate a changelog.

    Args:
        from_ref: Start ref.
        to_ref: End ref."""
    info("coming soon")


def review(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    since: str | None = typer.Option(None, "--since", help="Git ref to compare against"),
) -> None:
    """Review generated documentation.

    Args:
        path: Repository path.
        since: Git ref to compare against."""
    info("coming soon")


def init(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Initialize a new repository.

    Args:
        path: Repository path.
        dry_run: Preview without writing."""
    info("coming soon")
