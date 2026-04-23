import questionary
from questionary import Style as QStyle
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from docspatch.graph.state import DocpatchState

console = Console()

_Q_STYLE = QStyle(
    [
        ("qmark", "fg:#00d7ff bold"),
        ("question", "bold"),
        ("answer", "fg:#00d7ff bold"),
        ("pointer", "fg:#00d7ff bold"),
        ("highlighted", "fg:#00d7ff bold"),
        ("selected", "fg:#00d7ff"),
        ("instruction", "fg:#555555 italic"),
    ]
)


def _display_doc(doc: dict, index: int, total: int) -> None:
    fn_name = doc["name"]
    fn_file = doc.get("file", "")
    docstring = doc.get("generated_doc", "")

    title = Text()
    title.append(f"{index}/{total}  ", style="dim")
    title.append(f"{fn_name}()", style="bold cyan")

    subtitle = Text(fn_file, style="dim")
    body = Text(docstring.strip())

    console.print()
    console.print(
        Panel(body, title=title, subtitle=subtitle, border_style="cyan", padding=(0, 1))
    )


def _display_bulk_summary(docs: list[dict]) -> None:
    table = Table(show_header=True, header_style="bold dim", box=None, padding=(0, 2))
    table.add_column("Function", style="cyan", no_wrap=True)
    table.add_column("Preview", style="dim")
    for doc in docs:
        first_line = doc.get("generated_doc", "").strip().split("\n")[0][:80]
        table.add_row(f"{doc['name']}()", first_line)
    console.print()
    console.print(table)
    console.print()


def preview_all(state: DocpatchState) -> dict:
    docs = state["generated_docs"]
    total = len(docs)

    if not docs:
        return {"accepted_docs": [], "skipped_docs": [], "rerun_docs": []}

    accepted: list[dict] = []
    rerun: list[dict] = []

    console.print(f"\n  [bold]{total} doc(s) ready for review[/bold]")

    # Bulk accept shortcut
    bulk = questionary.select(
        "Review mode:",
        choices=["Accept all", "Review individually"],
        style=_Q_STYLE,
    ).ask()

    if not bulk or bulk == "Accept all":
        _display_bulk_summary(docs)
        return {"accepted_docs": docs, "skipped_docs": [], "rerun_docs": []}

    # Individual review
    for i, doc in enumerate(docs, 1):
        _display_doc(doc, i, total)

        action = questionary.select(
            "Action:",
            choices=[
                "Accept",
                "Edit manually  — write it yourself, no LLM",
                "Regenerate    — tell the LLM what to fix",
                "Discard       — skip, do not write",
            ],
            style=_Q_STYLE,
        ).ask()

        if action and action.startswith("Accept"):
            accepted.append(doc)
        elif action and action.startswith("Edit manually"):
            edited = questionary.text(
                "Docstring:",
                default=doc.get("generated_doc", ""),
                style=_Q_STYLE,
            ).ask()
            accepted.append({**doc, "generated_doc": edited.strip() if edited and edited.strip() else doc.get("generated_doc", "")})
        elif action and action.startswith("Regenerate"):
            feedback = questionary.text(
                "What's missing or wrong?",
                style=_Q_STYLE,
            ).ask()
            rerun.append({**doc, "feedback": feedback.strip() if feedback and feedback.strip() else "improve this docstring"})
        # Discard: drop silently

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
