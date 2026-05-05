"""Interactive handlers for docstring pipeline interrupts and review sessions."""

import questionary
from rich.panel import Panel
from rich.table import Table

from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import ReviewSessionResult, SizeCheckInterrupt
from src.utils.log import get_logger
from src.utils.ui import Q_STYLE, console, info, short_path, step, warn

__all__ = [
    "ReviewCancelled",
    "handle_file_pick_interrupt",
    "handle_size_check_interrupt",
    "run_review_session",
]

logger = get_logger(__name__)


class ReviewCancelled(Exception):
    """Raised when the user interrupts a review session mid-way."""

    def __init__(self, accepted_so_far: dict[str, str]) -> None:
        super().__init__()
        self.accepted_so_far = accepted_so_far


async def handle_size_check_interrupt(iv: SizeCheckInterrupt) -> str:
    """Show size panel, present strategy choices, return chosen strategy string."""
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
    """Present file checkbox; return chosen file paths."""
    chosen: list[str] | None = await questionary.checkbox(
        "Select files to document (use Space to select):", choices=files, style=Q_STYLE
    ).ask_async()
    return chosen or []


async def run_review_session(docs: dict[str, str], catalog: dict[str, FunctionMetadata]) -> ReviewSessionResult:
    """Interactive async review loop — accept, edit, rerun, or skip each docstring."""
    if not docs:
        return {"accepted": {}, "rerun": [], "feedback": {}}

    table = Table(title="Generated Docstrings Summary", show_header=True, header_style="bold indian_red", box=None)
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
        rerun_table = Table(title="Functions Queued for Rerun", show_header=True, header_style="bold yellow", box=None)
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
