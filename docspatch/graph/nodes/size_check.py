import questionary
from questionary import Style as QStyle
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from docspatch.graph.state import DocpatchState

console = Console()

LARGE_THRESHOLD = 50
TOKENS_PER_FN = 300

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


def _prompt_strategy(n_functions: int, n_files: int, token_estimate: int) -> str:
    cost_estimate = (token_estimate / 1_000_000) * 1.00

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

    choice = questionary.select(
        "How to proceed:",
        choices=[
            "Auto-batch — process all in chunks",
            "Pick files — choose which files",
            "Smart — only undocumented functions",
            "Quit",
        ],
        style=_Q_STYLE,
    ).ask()

    if not choice or choice.startswith("Quit"):
        return "q"
    if choice.startswith("Pick"):
        return "p"
    if choice.startswith("Smart"):
        return "s"
    return "a"


def _pick_files(functions: list[dict]) -> list[dict]:
    files = sorted({fn["file"] for fn in functions})
    chosen = questionary.checkbox(
        "Select files to process:",
        choices=files,
        style=_Q_STYLE,
    ).ask()

    if not chosen:
        console.print("  [yellow]No selection — processing all.[/yellow]")
        return functions
    chosen_set = set(chosen)
    return [fn for fn in functions if fn["file"] in chosen_set]


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
