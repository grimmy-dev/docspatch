"""config command — display and edit persistent settings."""

import os
import subprocess

import questionary
import typer

from src.utils.config import load, save
from src.utils.ui import Q_STYLE, cli_error_handler, step

__all__ = ["config"]

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


def _mask_key(key: str | None) -> str:
    """Return a masked API key string safe for display."""
    if not key:
        return "[dim]not set[/dim]"
    if len(key) <= 8:
        return "[green]●●●●[/green]"
    return f"[green]{key[:4]}...{key[-4:]}[/green]"


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
        keys_table.add_row(provider, _mask_key(key_val))

    from src.utils.ui import console

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
