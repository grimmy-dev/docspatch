"""Interactive handlers for README pipeline review and context preview."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import questionary
from rich.panel import Panel

from src.utils.ui import Q_STYLE, console, step

__all__ = ["handle_readme_review_interrupt", "offer_readme_context_view"]


async def handle_readme_review_interrupt(content: str, style: str = "compact") -> str | None:
    """Show generated README preview; return accepted content or None to abort."""
    preview = content[:2000] + "\n\n[…truncated…]" if len(content) > 2000 else content
    token_var = "readme_tokens_compact" if style == "compact" else "readme_tokens_detailed"
    console.print()
    console.print(Panel(preview, title="[bold]Generated README[/bold]", border_style="cyan", expand=False))
    console.print(f"\n[dim]Output capped by {token_var} — run dp config and edit {token_var} for longer output.[/dim]")

    action: str | None = await questionary.select(
        "README review:",
        choices=["Accept", "Edit — open in $EDITOR", "View full", "Abort"],
        style=Q_STYLE,
    ).ask_async()

    if action is None or action == "Abort":
        return None
    if action == "Accept":
        step("README accepted")
        return content
    if action == "View full":
        console.print(Panel(content, title="[bold]Full README[/bold]", border_style="cyan"))
        confirm: bool | None = await questionary.confirm("Accept this README?", default=True, style=Q_STYLE).ask_async()
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


async def offer_readme_context_view(prompt: str) -> None:
    """Offer to view the full prepared LLM context after a dry run."""
    from src.utils.prompts import README_SYSTEM

    view: bool | None = await questionary.confirm("View full prepared LLM context?", default=False, style=Q_STYLE).ask_async()
    if view:
        console.print(
            Panel(
                f"{README_SYSTEM}\n\n---\n\n{prompt}",
                title="[bold]Full LLM Context[/bold]",
                border_style="dim",
                expand=False,
            )
        )
