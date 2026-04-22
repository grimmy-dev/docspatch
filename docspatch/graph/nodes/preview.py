from rich.console import Console
from rich.panel import Panel

from docspatch.graph.state import DocpatchState

console = Console()


def _show_doc_panel(doc: dict, index: int, total: int) -> None:
    fn_name = doc["name"]
    docstring = doc.get("generated_doc", "")
    title = f"[bold]{index}/{total}[/bold]  {fn_name}()"
    console.print(Panel(docstring, title=title, border_style="blue"))


def _prompt_choice(prompt: str, valid: set[str]) -> str:
    while True:
        choice = input(f"\n  {prompt}: ").strip().lower()
        if choice in valid:
            return choice
        console.print(f"  [red]Enter one of: {', '.join(sorted(valid))}[/red]")


def preview_all(state: DocpatchState) -> dict:
    """Show all generated docs. Bulk accept, individual review, or quit."""
    docs = state["generated_docs"]
    total = len(docs)

    if not docs:
        return {"accepted_docs": [], "skipped_docs": []}

    console.print()
    for i, doc in enumerate(docs, 1):
        _show_doc_panel(doc, i, total)

    choice = _prompt_choice("Accept all? [y] review individually [r] quit [q]", {"y", "r", "q"})

    if choice == "q":
        raise SystemExit(0)

    if choice == "y":
        return {"accepted_docs": docs, "skipped_docs": []}

    # individual review
    accepted, skipped = [], []
    for i, doc in enumerate(docs, 1):
        console.print()
        _show_doc_panel(doc, i, total)
        action = _prompt_choice("[a]ccept  [s]kip", {"a", "s"})
        (accepted if action == "a" else skipped).append(doc)

    return {"accepted_docs": accepted, "skipped_docs": skipped}


def collect_feedback(state: DocpatchState) -> dict:
    """For each skipped doc ask what's wrong. Populate rerun_docs."""
    rerun: list[dict] = []

    console.print()
    for doc in state["skipped_docs"]:
        fn_name = doc["name"]
        existing = doc.get("generated_doc", "")
        console.print(
            Panel(
                f'[dim]Current:[/dim] "{existing}"',
                title=f"{fn_name}()",
                border_style="yellow",
            )
        )
        feedback = input("  What's wrong?: ").strip()
        if feedback:
            rerun.append({**doc, "feedback": feedback})

    return {"rerun_docs": rerun, "feedback": {d["name"]: d["feedback"] for d in rerun}}


# --- routing ---

def has_skipped(state: DocpatchState) -> str:
    return "rerun" if state.get("skipped_docs") else "done"


def prompt_rerun(state: DocpatchState) -> dict:
    """Ask user if they want to rerun skipped docs with feedback."""
    if state.get("dry_run") or not state.get("skipped_docs"):
        return {}
    n = len(state["skipped_docs"])
    console.print()
    choice = _prompt_choice(f"{n} skipped. Rerun with feedback? [y/n]", {"y", "n"})
    if choice == "n":
        return {"skipped_docs": []}
    return {}
