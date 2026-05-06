"""Interactive handlers for README pipeline review."""

from src.cli.ui_handlers.common import handle_review_interrupt

__all__ = ["handle_readme_review_interrupt"]


async def handle_readme_review_interrupt(content: str, style: str = "compact") -> str | None:
    """Show generated README preview; return accepted content or None to abort."""
    token_var = "readme_tokens_compact" if style == "compact" else "readme_tokens_detailed"
    hint = f"\n[dim]Output capped by {token_var} — run dp config and edit {token_var} for longer output.[/dim]"
    return await handle_review_interrupt(content, title="README", prompt_label="README review", hint=hint)
