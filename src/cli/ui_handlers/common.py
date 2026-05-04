"""Shared interactive handlers used across pipelines."""

import asyncio

import questionary

from src.utils.config import load
from src.utils.ui import Q_STYLE, step

__all__ = ["interactive_model_switch"]


async def interactive_model_switch() -> str:
    """Offer action after a rate-limit hit; returns 'wait', 'switch', or 'abort'."""
    from src.cli.provider import configure_provider
    from src.utils.config import save

    action: str | None = await questionary.select(
        "Rate limit hit. What next?",
        choices=[
            questionary.Choice("wait ~60s and retry", value="wait"),
            questionary.Choice("switch model/provider", value="switch"),
            questionary.Choice("abort", value="abort"),
        ],
        style=Q_STYLE,
    ).ask_async()

    if action is None or action == "abort":
        return "abort"
    if action == "switch":
        cfg = load()
        updated = await asyncio.to_thread(configure_provider, cfg)
        if updated:
            save(updated)
            step("Provider updated")
        return "switch"
    return "wait"
