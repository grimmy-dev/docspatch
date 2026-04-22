from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from docspatch.graph.state import DocpatchState

console = Console()

LARGE_THRESHOLD = 50  # functions
TOKENS_PER_FN = 300  # rough estimate: ~200 input + ~100 output


def _prompt_strategy(n_functions: int, n_files: int, token_estimate: int) -> str:
    cost_estimate = (token_estimate / 1_000_000) * 1.00  # ~$1/1M blended

    warning = Text.assemble(
        ("⚠  Large repo detected", "bold yellow"),
        f" — {n_functions} functions across {n_files} files\n",
        ("   Estimated tokens: ", "dim"),
        (f"~{token_estimate:,}", "cyan"),
        ("  (~$", "dim"),
        (f"{cost_estimate:.2f}", "cyan"),
        (")", "dim"),
    )
    console.print(Panel(warning, border_style="yellow"))
    console.print(
        "  [bold][a][/bold] auto-batch  — process in chunks\n"
        "  [bold][p][/bold] pick files  — choose which files now\n"
        "  [bold][s][/bold] smart       — only undocumented functions\n"
        "  [bold][q][/bold] quit"
    )

    while True:
        choice = input("\n  Choice: ").strip().lower()
        if choice in ("a", "p", "s", "q"):
            return choice
        console.print("  [red]Invalid choice.[/red] Enter a, p, s, or q.")


def _pick_files(functions: list[dict]) -> list[dict]:
    files = sorted({fn["file"] for fn in functions})
    console.print("\n  [bold]Select files to process:[/bold]")
    for i, path in enumerate(files, 1):
        console.print(f"  [{i}] {path}")

    raw = input("\n  Enter numbers (comma-separated): ").strip()
    try:
        indices = {int(x.strip()) - 1 for x in raw.split(",") if x.strip()}
        chosen = {files[i] for i in indices if 0 <= i < len(files)}
    except ValueError:
        chosen = set()

    if not chosen:
        console.print("  [yellow]No valid selection — processing all.[/yellow]")
        return functions
    return [fn for fn in functions if fn["file"] in chosen]


def size_check(state: DocpatchState) -> dict:
    functions = state["parsed_functions"]
    n_functions = len(functions)
    n_files = len({fn["file"] for fn in functions})
    token_estimate = n_functions * TOKENS_PER_FN

    # dry-run or --batch: skip interactive prompt entirely
    if state.get("dry_run") or state.get("needs_batching"):
        return {
            "needs_batching": True,
            "batch_strategy": "auto",
            "token_estimate": token_estimate,
        }

    if n_functions < LARGE_THRESHOLD:
        return {
            "needs_batching": False,
            "batch_strategy": "auto",
            "token_estimate": token_estimate,
        }

    choice = _prompt_strategy(n_functions, n_files, token_estimate)

    if choice == "q":
        raise SystemExit(0)

    strategy_map = {"a": "auto", "p": "pick", "s": "smart"}
    strategy = strategy_map[choice]

    if strategy == "smart":
        functions = [fn for fn in functions if not fn.get("existing_doc")]
    elif strategy == "pick":
        functions = _pick_files(functions)

    return {
        "needs_batching": True,
        "batch_strategy": strategy,
        "parsed_functions": functions,
        "token_estimate": token_estimate,
    }
