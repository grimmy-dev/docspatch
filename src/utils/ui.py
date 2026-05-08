"""Console output helpers and the cli_error_handler decorator."""

import sys
from collections.abc import Callable
from functools import wraps
from pathlib import Path

import typer
from questionary import Style as QStyle
from rich.console import Console

console = Console()

Q_STYLE = QStyle(
    [
        ("qmark", "fg:#cd853f bold"),
        ("question", "bold"),
        ("answer", "fg:#cd853f bold"),
        ("pointer", "fg:#cd853f bold"),
        ("highlighted", "fg:#cd853f bold"),
        ("selected", "fg:#cd853f"),
        ("separator", "fg:#555555"),
        ("instruction", "fg:#555555 italic"),
    ]
)


def cli_error_handler[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Decorator: translates domain exceptions into clean CLI messages.

    Args:
        func: The function to decorate.

    Returns:
        The decorated function.

    Raises:
        SystemExit: With code 130 for KeyboardInterrupt, code 1 for other exceptions.
                    Prints full traceback if --debug is in sys.argv."""

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except (typer.Exit, typer.Abort, SystemExit) as _:
            raise
        except KeyboardInterrupt as _:
            raise SystemExit(130) from None
        except Exception as exc:
            if "--debug" in sys.argv:
                console.print_exception()
            else:
                console.print(f"[red]Error:[/red] {exc}")
            raise SystemExit(1) from exc

    return wrapper


def short_path(filepath: Path | str) -> str:
    """Return parent/filename for display (e.g. src/utils/ui.py → utils/ui.py).

    Args:
        filepath: The file path to shorten.

    Returns:
        The shortened file path string."""
    p = Path(filepath)
    return f"{p.parent.name}/{p.name}"


def step(name: str, detail: str = "") -> None:
    """Print a green checkmark step with optional dim detail.

    Args:
        name: The main step name.
        detail: Optional detailed information for the step."""
    msg = f"[green]✓[/green] {name}"
    if detail:
        msg += f"  [dim]{detail}[/dim]"
    console.print(msg)


def warn(msg: str) -> None:
    """Print a yellow warning message.

    Args:
        msg: The warning message to print."""
    console.print(f"[yellow]⚠[/yellow]  {msg}")


def error(msg: str) -> None:
    """Print a red error message.

    Args:
        msg: The error message to print."""
    console.print(f"[red]✗[/red]  {msg}")


def info(msg: str) -> None:
    """Print a dim informational message.

    Args:
        msg: The message to print."""
    console.print(f"[dim]{msg}[/dim]")
