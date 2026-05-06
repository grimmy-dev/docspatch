"""Shared interactive handlers used across pipelines."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import questionary
from rich.panel import Panel

from src.utils.config import load
from src.utils.ui import Q_STYLE, console, copy_to_clipboard, step

__all__ = [
    "handle_review_interrupt",
    "interactive_model_switch",
    "offer_context_view",
    "open_in_editor",
]


async def open_in_editor(content: str) -> str | None:
    """Open content in $VISUAL/$EDITOR/vi; return edited text or None if result is empty."""
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR") or "vi"
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False, encoding="utf-8") as f:
        f.write(content)
        tmp_path = f.name
    try:
        await asyncio.to_thread(lambda: subprocess.run([editor, tmp_path]))
        edited = await asyncio.to_thread(lambda: Path(tmp_path).read_text(encoding="utf-8"))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return edited if edited.strip() else None


async def handle_review_interrupt(
    content: str,
    *,
    title: str,
    prompt_label: str,
    hint: str | None = None,
) -> str | None:
    """Interactive review prompt for generated content; return accepted content or None to abort.

    Args:
        content: Generated content to review.
        title: Display label used in panel titles and step messages (e.g. 'Changelog Entry').
        prompt_label: Prefix for the questionary prompt (e.g. 'Changelog review').
        hint: Optional message printed below the preview panel.
    """
    preview = content[:2000] + "\n\n[…truncated…]" if len(content) > 2000 else content
    console.print()
    console.print(Panel(preview, title=f"[bold]Generated {title}[/bold]", border_style="cyan", expand=False))
    if hint:
        console.print(hint)

    action: str | None = await questionary.select(
        f"{prompt_label}:",
        choices=[
            questionary.Choice("Accept", value="accept"),
            questionary.Choice("Copy to clipboard", value="copy"),
            questionary.Choice("Edit — open in $EDITOR", value="edit"),
            questionary.Choice("View full", value="view"),
            questionary.Choice("Abort", value="abort"),
        ],
        style=Q_STYLE,
    ).ask_async()

    if action is None or action == "abort":
        return None
    if action == "accept":
        step(f"{title} accepted")
        return content
    if action == "copy":
        ok = await asyncio.to_thread(copy_to_clipboard, content)
        console.print("[green]Copied to clipboard.[/green]" if ok else "[yellow]Clipboard unavailable.[/yellow]")
        return content
    if action == "view":
        console.print(Panel(content, title=f"[bold]Full {title}[/bold]", border_style="cyan"))
        confirm: bool | None = await questionary.confirm(f"Accept this {title}?", default=True, style=Q_STYLE).ask_async()
        return content if confirm else None
    return await open_in_editor(content)


async def offer_context_view(full_context: str) -> None:
    """Offer to view or copy the full assembled LLM context after a dry run.

    Args:
        full_context: Pre-assembled system prompt + user prompt (caller owns construction).
    """
    action: str | None = await questionary.select(
        "LLM context:",
        choices=[
            questionary.Choice("View full", value="view"),
            questionary.Choice("Copy to clipboard", value="copy"),
            questionary.Choice("Skip", value="skip"),
        ],
        style=Q_STYLE,
    ).ask_async()

    if action is None or action == "skip":
        return

    if action == "copy":
        ok = await asyncio.to_thread(copy_to_clipboard, full_context)
        console.print("[green]Copied to clipboard.[/green]" if ok else "[yellow]Clipboard unavailable.[/yellow]")
    elif action == "view":
        console.print(Panel(full_context, title="[bold]Full LLM Context[/bold]", border_style="dim", expand=False))


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
