"""Interactive UI handlers for LangGraph interrupts."""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import questionary
from rich.panel import Panel
from rich.table import Table

from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import ReviewSessionResult, SizeCheckInterrupt
from src.utils.config import load
from src.utils.log import get_logger
from src.utils.ui import Q_STYLE, console, info, short_path, step, warn

logger = get_logger(__name__)


async def handle_size_check_interrupt(iv: SizeCheckInterrupt) -> str:
    """Handles interrupts related to file size checks.

    Shows size panel, presents strategy choices, and returns the chosen strategy string.

    Args:
        iv: The SizeCheckInterrupt object containing file count, token estimate, and threshold.

    Returns:
        A string representing the chosen strategy."""
    n = iv.get("file_count", 0)
    est = iv.get("token_estimate", 0)
    threshold = iv.get("threshold", 0)

    console.print(f"\n[bold yellow]Large codebase:[/bold yellow] {n} functions detected (threshold: {threshold}, ~{est:,} tokens)\n")

    choice: str | None = await questionary.select(
        "How to proceed?",
        choices=[
            questionary.Choice("auto  — document everything", value="auto"),
            questionary.Choice("smart — undocumented functions only", value="smart"),
            questionary.Choice("pick  — choose files interactively", value="pick"),
            questionary.Choice("quit  — exit without changes", value="quit"),
        ],
        style=Q_STYLE,
    ).ask_async()

    return choice if choice is not None else "quit"


async def handle_file_pick_interrupt(files: list[str]) -> list[str]:
    """Present file checkbox; return chosen file paths.

    Args:
        files: List of files to choose from.

    Returns:
        List of chosen file paths."""
    chosen: list[str] | None = await questionary.checkbox(
        "Select files to document (use Space to select):", choices=files, style=Q_STYLE
    ).ask_async()
    return chosen or []


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


class ReviewCancelled(Exception):
    def __init__(self, accepted_so_far: dict[str, str]) -> None:
        """Initializes the ReviewSession.

        Args:
            accepted_so_far: A dictionary of already accepted function documentation."""
        super().__init__()
        self.accepted_so_far = accepted_so_far


async def run_review_session(docs: dict[str, str], catalog: dict[str, FunctionMetadata]) -> ReviewSessionResult:
    """Interactive async review loop with Rich UI components.

    Args:
        docs: Dictionary of function names to their documentation.
        catalog: Dictionary of function names to their metadata.

    Returns:
        A ReviewSessionResult containing accepted changes, functions to rerun, and feedback."""
    if not docs:
        return {"accepted": {}, "rerun": [], "feedback": {}}

    table = Table(
        title="Generated Docstrings Summary",
        show_header=True,
        header_style="bold indian_red",
        box=None,
    )
    table.add_column("File", style="dim")
    table.add_column("Functions", style="bold", overflow="fold")

    by_file: dict[str, list[str]] = {}
    for fid in docs:
        fn = catalog[fid]
        by_file.setdefault(str(fn.file_path), []).append(fn.name)

    for filepath, fns in sorted(by_file.items()):
        table.add_row(short_path(filepath), ", ".join(fns))

    console.print()
    console.print(table)
    console.print()

    bulk: str | None = await questionary.select(
        f"How would you like to proceed? ({len(docs)} docstring{'s' if len(docs) != 1 else ''})",
        choices=["Review one by one", "Accept all"],
        style=Q_STYLE,
    ).ask_async()

    if bulk is None:
        return {"accepted": {}, "rerun": [], "feedback": {}}

    if bulk == "Accept all":
        step(f"Accepted {len(docs)} docstring(s)")
        logger.debug("run_review_session: bulk accepted %d docs", len(docs))
        return {"accepted": docs, "rerun": [], "feedback": {}}

    accepted: dict[str, str] = {}
    rerun: list[str] = []
    feedback: dict[str, str] = {}

    info("Ctrl+C at any time to stop review and keep accepted so far.")

    total = len(docs)
    try:
        for idx, (fid, docstring) in enumerate(docs.items(), 1):
            fn = catalog[fid]
            content = f"[dim]{fn.signature}[/dim]\n\n{docstring or '[italic](no doc generated)[/italic]'}"

            panel = Panel(
                content,
                title=f"[bold indian_red]{fn.name}[/bold indian_red]  [dim]{idx}/{total}[/dim]",
                subtitle=f"[dim]{short_path(fn.file_path)}[/dim]",
                border_style="indian_red",
                expand=False,
            )
            console.print()
            console.print(panel)

            action: str | None = await questionary.select(
                "Action:",
                choices=["Accept", "Edit — modify manually", "Rerun — send back to LLM", "Skip"],
                style=Q_STYLE,
            ).ask_async()

            if action is None:
                raise ReviewCancelled(accepted)

            if action == "Accept":
                accepted[fid] = docstring
                step(f"Accepted {fn.name}")

            elif action and action.startswith("Edit"):
                edited: str | None = await questionary.text("Edit docstring:", default=docstring, style=Q_STYLE).ask_async()
                if edited:
                    accepted[fid] = edited
                    step(f"Accepted {fn.name} (edited)")
                else:
                    info(f"Skipped {fn.name} (edit cancelled)")

            elif action and action.startswith("Rerun"):
                note: str | None = await questionary.text("Guide the LLM (optional, e.g. 'be more concise'):", style=Q_STYLE).ask_async()
                rerun.append(fid)
                if note:
                    feedback[fid] = note
                info(f"Queued {fn.name} for rerun")

            else:
                info(f"Skipped {fn.name}")

    except ReviewCancelled as exc:
        warn(f"Review cancelled — {len(exc.accepted_so_far)} accepted so far")
        return {"accepted": exc.accepted_so_far, "rerun": [], "feedback": {}}

    if rerun:
        rerun_table = Table(
            title="Functions Queued for Rerun",
            show_header=True,
            header_style="bold yellow",
            box=None,
        )
        rerun_table.add_column("Function", style="indian_red")
        rerun_table.add_column("Feedback", style="dim")

        for fid in rerun:
            rerun_table.add_row(catalog[fid].name, feedback.get(fid, "(no feedback provided)"))

        console.print()
        console.print(rerun_table)

        proceed: bool = await questionary.confirm("Proceed with LLM rerun?", default=True, style=Q_STYLE).ask_async()
        if not proceed:
            info("Rerun cancelled. Proceeding with accepted docs only.")
            rerun = []
            feedback = {}

    skipped = len(docs) - len(accepted) - len(rerun)
    logger.debug("run_review_session: accepted=%d rerun=%d skipped=%d", len(accepted), len(rerun), skipped)
    return {"accepted": accepted, "rerun": rerun, "feedback": feedback}


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
