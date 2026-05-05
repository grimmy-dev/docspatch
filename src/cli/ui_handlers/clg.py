"""Interactive handlers for changelog pipeline review and context preview."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import questionary
from rich.panel import Panel

from src.utils.ui import Q_STYLE, console, step

__all__ = ["handle_clg_review_interrupt", "offer_clg_context_view"]


async def handle_clg_review_interrupt(content: str) -> str | None:
    """Show generated changelog entry; return accepted content or None to abort."""
    preview = content[:2000] + "\n\n[…truncated…]" if len(content) > 2000 else content
    console.print()
    console.print(Panel(preview, title="[bold]Generated Changelog Entry[/bold]", border_style="cyan", expand=False))

    action: str | None = await questionary.select(
        "Changelog review:",
        choices=["Accept", "Edit — open in $EDITOR", "View full", "Abort"],
        style=Q_STYLE,
    ).ask_async()

    if action is None or action == "Abort":
        return None
    if action == "Accept":
        step("Changelog entry accepted")
        return content
    if action == "View full":
        console.print(Panel(content, title="[bold]Full Changelog Entry[/bold]", border_style="cyan"))
        confirm: bool | None = await questionary.confirm("Accept this entry?", default=True, style=Q_STYLE).ask_async()
        return content if confirm else None

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


async def offer_clg_context_view(prompt: str) -> None:
    """Offer to view or copy the full assembled LLM context after a dry run."""
    from src.utils.prompts import CHANGELOG_SYSTEM
    from src.utils.ui import copy_to_clipboard

    action: str | None = await questionary.select(
        "LLM context:",
        choices=["View full", "Copy to clipboard", "Skip"],
        default="Skip",
        style=Q_STYLE,
    ).ask_async()

    if action is None or action == "Skip":
        return

    full_context = f"{CHANGELOG_SYSTEM}\n\n---\n\n{prompt}"

    if action in ("View full", "Copy to clipboard"):
        if action == "Copy to clipboard":
            ok = copy_to_clipboard(full_context)
            console.print("[green]Copied to clipboard.[/green]" if ok else "[yellow]Clipboard unavailable.[/yellow]")
        else:
            console.print(Panel(full_context, title="[bold]Full LLM Context[/bold]", border_style="dim", expand=False))
