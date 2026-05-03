"""CLI command definitions and async entry points."""

import asyncio
import os
import subprocess
from pathlib import Path

import questionary
import typer

from src.cli.provider import configure_provider, current_provider_name
from src.schemas.graph_io import GraphConfig
from src.schemas.state import DocpatchState
from src.utils.config import get_api_key, load, save
from src.utils.git import is_git_repo
from src.utils.ui import Q_STYLE, cli_error_handler, console, info, step

_CONFIG_LABELS: dict[str, str] = {
    "style": "Style",
    "model": "Model",
    "review_model": "Review model",
    "provider_key": "Provider",
    "batch_size": "Batch size",
    "batch_max_lines": "Batch max lines",
    "tokens_per_fn_compact": "Tokens/fn (compact)",
    "tokens_per_fn_detailed": "Tokens/fn (detailed)",
    "large_threshold": "Large repo threshold",
    "diff_cap": "Diff cap (lines)",
    "log_count": "Git log entries",
    "prune_after_days": "Cache prune after (days)",
    "readme_tokens_compact": "README tokens (compact)",
    "readme_tokens_detailed": "README tokens (detailed)",
}


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
    dry_run: bool = typer.Option(False, "--dry-run", help="Estimate tokens and cost without writing"),
    style: str | None = typer.Option(None, "--style", help="compact (one-liner) or detailed (full docstring). Default from config."),
    since: str | None = typer.Option(None, "--since", help="Only document functions changed since this git ref (e.g. HEAD~3, main)."),
    update: bool = typer.Option(False, "--update", help="Re-document all functions, including already documented ones"),
    resume: bool = typer.Option(False, "--resume", help="Resume a previously interrupted run (uses stable thread ID)"),
    check: bool = typer.Option(False, "--check", help="Exit 1 if any functions need docs — no LLM, safe for CI"),
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
        resume (bool): If True, resumes an interrupted run."""
    from src.cli.runner import make_thread, run_docstring
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
def config() -> None:
    """Display current configuration and offer edit/reset shortcuts."""
    from rich.table import Table

    from src.schemas.config import AppDefaults
    from src.utils.config import CONFIG_PATH

    cfg = load()

    settings_table = Table(show_header=False, box=None, padding=(0, 2))
    settings_table.add_column("Key", style="bold")
    settings_table.add_column("Value", style="sandy_brown")
    for k, v in cfg.defaults.model_dump().items():
        settings_table.add_row(_CONFIG_LABELS.get(k, k), str(v))

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

    choice: str | None = questionary.select(
        "Config settings",
        choices=[
            questionary.Choice(title="edit", value="edit", shortcut_key="e"),
            questionary.Choice(title="reset to defaults", value="reset", shortcut_key="r"),
            questionary.Choice(title="quit", value="quit", shortcut_key="q"),
        ],
        style=Q_STYLE,
        use_shortcuts=True,
    ).ask()

    if choice is None or choice == "quit":
        return

    if choice == "edit":
        if not CONFIG_PATH.exists():
            save(cfg)
        editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
        if editor:
            subprocess.run([editor, str(CONFIG_PATH)])
        else:
            typer.launch(str(CONFIG_PATH))
        step("Config saved.")

    elif choice == "reset":
        save(cfg.model_copy(update={"defaults": AppDefaults()}))
        step("Settings reset to defaults. API keys preserved.")


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


@cli_error_handler
def readme(
    path: Path = typer.Argument(Path("."), help="Repository or target directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show context summary and token estimate without calling LLM"),
    rewrite: bool = typer.Option(False, "--rewrite", help="Regenerate from scratch even if a README already exists"),
    output: Path | None = typer.Option(None, "--output", help="Write README to this path (default: README.md in target dir)"),
    style: str | None = typer.Option(None, "--style", help="compact (minimal) or detailed (badges, full sections). Default from config."),
    remarks: str | None = typer.Option(None, "--remarks", help="Extra instructions passed to LLM (e.g. 'add a development section')"),
) -> None:
    """Generate or update README.md for the repository.

    Args:
        path: Repository or target directory (scope support).
        dry_run: Preview without writing.
        rewrite: Regenerate from scratch even if README exists.
        output: Write README to this path.
        style: compact or detailed.
        remarks: Extra instructions passed directly to the LLM."""
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


def clg(
    from_ref: str = typer.Option("HEAD~1", "--from", help="Start ref"),
    to_ref: str = typer.Option("HEAD", "--to", help="End ref"),
) -> None:
    """Generate a changelog.

    Args:
        from_ref: Start ref.
        to_ref: End ref."""
    del from_ref, to_ref
    info("coming soon")


def review(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    since: str | None = typer.Option(None, "--since", help="Git ref to compare against"),
) -> None:
    """Review generated documentation.

    Args:
        path: Repository path.
        since: Git ref to compare against."""
    del path, since
    info("coming soon")


def init(
    path: Path = typer.Argument(Path("."), help="Repository path"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Initialize a new repository.

    Args:
        path: Repository path.
        dry_run: Preview without writing."""
    del path, dry_run
    info("coming soon")
