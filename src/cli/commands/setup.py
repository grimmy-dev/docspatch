"""setup command — interactive provider and style configuration."""

import questionary
import typer

from src.cli.provider import configure_provider, current_provider_name
from src.utils.config import load, save
from src.utils.ui import Q_STYLE, cli_error_handler, step

__all__ = ["setup"]


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
