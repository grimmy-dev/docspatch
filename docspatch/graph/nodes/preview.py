from pathlib import Path

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from docspatch.graph.state import DocpatchState
from docspatch.utils.ui import Q_STYLE, copy_to_clipboard

console = Console()

_FULL_FILE_PREVIEW_LINES = 20


def _ask(prompt) -> str:
    """Run a questionary prompt; exit cleanly if user presses Esc or Ctrl+C."""
    result = prompt.ask()
    if result is None:
        console.print("\n  [yellow]Cancelled.[/yellow]")
        raise SystemExit(0)
    return result


# --------------------------------------------------------------------------
# Display helpers
# --------------------------------------------------------------------------


def _short_path(filepath: str) -> str:
    parts = Path(filepath).parts
    return "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]


def _is_full_file(doc: dict) -> bool:
    return doc.get("line_start") is None


def _display_doc(doc: dict, index: int, total: int) -> None:
    name = doc["name"]
    content = doc.get("generated_doc", "").strip()
    file_path = doc.get("file", "")

    title = Text()
    title.append(f"{index}/{total}  ", style="dim")
    # Files don't get ()
    title.append(name if _is_full_file(doc) else f"{name}()", style="bold cyan")

    subtitle = Text(file_path, style="dim")

    console.print()
    console.print(
        Panel(
            Text(content),
            title=title,
            subtitle=subtitle,
            border_style="cyan",
            padding=(0, 1),
        )
    )


def _display_bulk_summary(docs: list[dict]) -> None:
    """Show all generated docs so the user knows what they're reviewing."""
    full_file = [d for d in docs if _is_full_file(d)]
    func_docs = [d for d in docs if not _is_full_file(d)]

    # README / CHANGELOG — truncated panel so content is visible
    for doc in full_file:
        content = doc.get("generated_doc", "").strip()
        lines = content.split("\n")
        preview = "\n".join(lines[:_FULL_FILE_PREVIEW_LINES])
        if len(lines) > _FULL_FILE_PREVIEW_LINES:
            preview += (
                f"\n\n[dim]… {len(lines) - _FULL_FILE_PREVIEW_LINES} more lines[/dim]"
            )
        console.print()
        console.print(
            Panel(
                preview,
                title=f"[bold cyan]{doc['name']}[/bold cyan]",
                border_style="cyan",
                padding=(0, 1),
            )
        )

    # Docstrings — compact table grouped by file
    if func_docs:
        by_file: dict[str, list[dict]] = {}
        for doc in func_docs:
            by_file.setdefault(doc.get("file", ""), []).append(doc)

        for filepath, file_docs in by_file.items():
            console.print(f"\n  [dim]{_short_path(filepath)}[/dim]")
            table = Table(show_header=False, box=None, padding=(0, 2))
            table.add_column("fn", style="cyan", no_wrap=True)
            table.add_column("preview", style="dim")
            for doc in file_docs:
                first_line = doc.get("generated_doc", "").strip().split("\n")[0][:72]
                table.add_row(f"  {doc['name']}()", first_line)
            console.print(table)

    console.print()


# --------------------------------------------------------------------------
# Action choice sets
# --------------------------------------------------------------------------

_ACTIONS_FUNC = [
    "Accept           — write to file as-is",
    "Edit             — modify text before writing",
    "Rerun            — give feedback, let LLM improve",
    "Discard          — skip, write nothing",
]

_ACTIONS_FILE = [
    "Accept           — write to file",
    "Edit             — modify before writing",
    "Copy to clipboard — save without writing",
    "Rerun            — give feedback, let LLM improve",
    "Discard          — skip",
]


# --------------------------------------------------------------------------
# Main preview node
# --------------------------------------------------------------------------


def preview_all(state: DocpatchState) -> dict:
    docs = state["generated_docs"]

    if not docs:
        return {"accepted_docs": [], "skipped_docs": [], "rerun_docs": []}

    # Always show content before asking — user sees what they're accepting
    _display_bulk_summary(docs)
    console.print(f"  [bold]{len(docs)} doc(s) ready[/bold]")

    bulk = _ask(
        questionary.select(
            "Review mode:",
            choices=["Accept all", "Review one by one"],
            instruction="(↑↓ navigate  ·  Enter select  ·  Esc cancel)",
            style=Q_STYLE,
        )
    )

    if bulk == "Accept all":
        return {"accepted_docs": docs, "skipped_docs": [], "rerun_docs": []}

    accepted: list[dict] = []
    rerun: list[dict] = []

    for i, doc in enumerate(docs, 1):
        _display_doc(doc, i, len(docs))

        choices = _ACTIONS_FILE if _is_full_file(doc) else _ACTIONS_FUNC
        action = _ask(questionary.select("What to do:", choices=choices, style=Q_STYLE))

        if action.startswith("Discard"):
            pass  # skip silently

        elif action.startswith("Accept"):
            accepted.append(doc)

        elif action.startswith("Edit"):
            edited = _ask(
                questionary.text(
                    "Edit content:",
                    default=doc.get("generated_doc", ""),
                    style=Q_STYLE,
                )
            )
            accepted.append(
                {
                    **doc,
                    "generated_doc": edited.strip()
                    if edited.strip()
                    else doc.get("generated_doc", ""),
                }
            )

        elif action.startswith("Copy"):
            ok = copy_to_clipboard(doc.get("generated_doc", ""))
            msg = (
                "Copied to clipboard."
                if ok
                else "Clipboard unavailable — copy from the preview above."
            )
            console.print(f"  [dim]{msg}[/dim]")

        elif action.startswith("Rerun"):
            feedback = _ask(questionary.text("What needs to change?", style=Q_STYLE))
            rerun.append(
                {
                    **doc,
                    "feedback": feedback.strip()
                    if feedback.strip()
                    else "improve this",
                }
            )

    n_accepted = len(accepted)
    n_rerun = len(rerun)
    parts = []
    if n_accepted:
        parts.append(f"[green]{n_accepted} accepted[/green]")
    if n_rerun:
        parts.append(f"[yellow]{n_rerun} queued for rerun[/yellow]")
    if not parts:
        parts.append("[dim]all skipped[/dim]")
    console.print("  " + "  ".join(parts) + "\n")

    return {
        "accepted_docs": accepted,
        "skipped_docs": [],
        "rerun_docs": rerun,
        "feedback": {d["name"]: d["feedback"] for d in rerun},
    }


def has_rerun(state: DocpatchState) -> str:
    return "rerun" if state.get("rerun_docs") else "done"
