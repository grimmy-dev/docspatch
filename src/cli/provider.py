"""Interactive provider/model selection helpers used by setup and config."""

from typing import cast

import questionary

from src.schemas.config import AppConfig, AppDefaults, ProviderConfig
from src.utils.providers import CUSTOM, PROVIDERS
from src.utils.ui import Q_STYLE, console


def pick_model(label: str, choices: list[str]) -> str | None:
    """Interactive model picker with a custom-entry fallback; returns None on Esc.

    Args:
        label: The question label.
        choices: A list of choices.

    Returns:
        The selected model name or None if Esc is pressed."""
    selection = questionary.select(label, choices=[*choices, CUSTOM], style=Q_STYLE).ask()
    if selection is None:
        return None
    if selection == CUSTOM:
        custom = questionary.text("Model name:", style=Q_STYLE).ask()
        return custom if custom else None
    return cast(str, selection)


def current_provider_name(cfg: AppConfig) -> str:
    """Return the display name of the currently configured provider.

    Args:
        cfg: AppConfig object.

    Returns:
        The provider name."""
    return cfg.defaults.provider_key


def configure_provider(cfg: AppConfig) -> AppConfig | None:
    """Walk the user through provider, API key, and model selection.

    Returns an updated AppConfig, or None if the user cancels at any step.
    Every Esc is handled explicitly — no partial writes.

    Args:
        cfg: AppConfig object.

    Returns:
        An updated AppConfig or None."""
    console.print(f"[dim]Current: {cfg.defaults.provider_key} · model: {cfg.defaults.model} · review: {cfg.defaults.review_model}[/dim]\n")

    name = questionary.select("Provider:", choices=list(PROVIDERS.keys()), style=Q_STYLE).ask()
    if name is None:
        return None

    provider: ProviderConfig = PROVIDERS[name]
    existing: str | None = getattr(cfg.keys, provider.key_field, None)
    api_key: str | None = None

    if existing:
        reuse = questionary.confirm(f"Reuse {name} key ({existing[:4]}…)?", style=Q_STYLE).ask()
        if reuse is None:
            return None
        api_key = existing if reuse else None

    if api_key is None:
        api_key = questionary.password(f"{name} API key:", style=Q_STYLE).ask()
        if not api_key:
            return None

    model = pick_model("Generation model:", provider.models)
    if model is None:
        return None

    rev = pick_model("Review model:", provider.review_models)
    if rev is None:
        return None

    new_keys = cfg.keys.model_copy(update={provider.key_field: api_key})
    new_defaults: AppDefaults = cfg.defaults.model_copy(update={"provider_key": name, "model": model, "review_model": rev})
    return cfg.model_copy(update={"defaults": new_defaults, "keys": new_keys})
