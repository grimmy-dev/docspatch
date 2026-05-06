"""Interactive handlers for changelog pipeline review."""

from src.cli.ui_handlers.common import handle_review_interrupt

__all__ = ["handle_clg_review_interrupt"]


async def handle_clg_review_interrupt(content: str) -> str | None:
    """Show generated changelog entry; return accepted content or None to abort."""
    return await handle_review_interrupt(content, title="Changelog Entry", prompt_label="Changelog review")
