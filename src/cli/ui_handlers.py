"""Interactive UI handlers for LangGraph interrupts."""

import asyncio

from rich.panel import Panel
from rich.table import Table

from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import ReviewSessionResult, SizeCheckInterrupt
from src.schemas.state import DocpatchState
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
    import questionary

    n = iv.get("file_count", 0)
    est = iv.get("token_estimate", 0)
    threshold = iv.get("threshold", 0)

    console.print(f"""\n[bold yellow]Large repo:[/bold yellow] {n} functions (threshold: {threshold}, ~{est:,} tokens)\n""")

    choice: str | None = await questionary.select(
        "How to proceed?",
        choices=[
            "auto   — process everything",
            "smart  — undocumented only",
            "pick   — choose files",
            "quit   — exit",
        ],
        style=Q_STYLE,
    ).ask_async()

    if choice is None:
        return "quit"
    return choice.split()[0]


async def handle_file_pick_interrupt(files: list[str]) -> list[str]:
    """Present file checkbox; return chosen file paths.

    Args:
        files: List of files to choose from.

    Returns:
        List of chosen file paths."""
    import questionary

    chosen: list[str] | None = await questionary.checkbox(
        "Select files to document (use Space to select):", choices=files, style=Q_STYLE
    ).ask_async()
    return chosen or []


async def interactive_model_switch() -> str:
    """Offer action after a rate-limit hit; returns 'wait', 'switch', or 'abort'."""
    import questionary

    from src.cli.provider import configure_provider
    from src.utils.config import save

    action: str | None = await questionary.select(
        "Rate limit hit. What next?",
        choices=["wait ~60s and retry", "switch model/provider", "abort"],
        style=Q_STYLE,
    ).ask_async()

    if action is None or "abort" in action:
        return "abort"
    if "switch" in action:
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
    import questionary

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
        "How would you like to proceed?",
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

    try:
        for fid, docstring in docs.items():
            fn = catalog[fid]
            content = f"[dim]{fn.signature}[/dim]\n\n{docstring or '[italic](no doc generated)[/italic]'}"

            panel = Panel(
                content,
                title=f"[bold indian_red]{fn.name}[/bold indian_red]",
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


def print_dry_run_breakdown(state: DocpatchState) -> None:
    """Show per-file token breakdown for --dry-run."""
    cfg = load()
    style = state.style
    output_per_fn = cfg.defaults.tokens_per_fn_compact if style == "compact" else cfg.defaults.tokens_per_fn_detailed
    cost_per_m = 1.00

    by_file: dict[str, list[str]] = {}
    for fid in state.significant_functions:
        fn = state.catalog[fid]
        by_file.setdefault(str(fn.file_path), []).append(fid)

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("file", style="dim")
    table.add_column("fns", justify="right")
    table.add_column("~tokens", justify="right", style="sandy_brown")
    table.add_column("~cost", justify="right", style="dim")

    total_fns = 0
    total_tokens = 0
    for filepath, fids in sorted(by_file.items()):
        n = len(fids)
        t = sum((state.catalog[fid].end_line - state.catalog[fid].start_line + 1) * 10 + output_per_fn for fid in fids)
        total_fns += n
        total_tokens += t
        table.add_row(short_path(filepath), str(n), f"{t:,}", f"${(t / 1_000_000) * cost_per_m:.4f}")

    table.add_row("", "", "", "")
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_fns}[/bold]",
        f"[bold sandy_brown]{total_tokens:,}[/bold sandy_brown]",
        f"[bold]${(total_tokens / 1_000_000) * cost_per_m:.3f}[/bold]",
    )
    console.print("\n[bold]Dry Run Estimation[/bold]")
    console.print(table)


def print_check_results(significant: list[str], catalog: dict[str, FunctionMetadata]) -> None:
    """Display table of functions that need documentation."""
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("File", style="dim")
    table.add_column("Function", style="bold")
    table.add_column("Reason", style="yellow")

    for fid in significant:
        fn = catalog[fid]
        reason = "missing docstring" if not fn.docstring else "body changed"
        table.add_row(short_path(fn.file_path), fn.name, reason)

    console.print("\n[bold red]Undocumented or changed functions:[/bold red]")
    console.print(table)
    console.print(f"\n[red]{len(significant)} function(s) need documentation.[/red]")
