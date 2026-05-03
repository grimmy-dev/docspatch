"""Console output helpers and the cli_error_handler decorator."""

import os
import subprocess
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


def copy_to_clipboard(text: str) -> bool:
    """Copy text to the system clipboard; returns False when unavailable.

    Linux: requires DISPLAY or WAYLAND_DISPLAY and xclip or xsel.
    macOS: uses pbcopy.
    Windows: uses ctypes directly — no external dependency.

    Args:
        text: The text to copy to the clipboard.

    Returns:
        True if the text was successfully copied, False otherwise."""
    if sys.platform == "linux":
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False
        for cmd in (
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            try:
                subprocess.run(cmd, input=text.encode(), check=True, capture_output=True)
                return True
            except (FileNotFoundError, subprocess.CalledProcessError) as _:
                continue
        return False

    if sys.platform == "darwin":
        try:
            subprocess.run(["pbcopy"], input=text.encode(), check=True, capture_output=True)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError) as _:
            return False

    if sys.platform == "win32":
        try:
            import ctypes

            # CF_UNICODETEXT = 13; GMEM_MOVEABLE = 0x0002
            ctypes.windll.user32.OpenClipboard(0)  # type: ignore[attr-defined]
            ctypes.windll.user32.EmptyClipboard()  # type: ignore[attr-defined]
            encoded = text.encode("utf-16-le") + b"\x00\x00"
            handle = ctypes.windll.kernel32.GlobalAlloc(0x0002, len(encoded))  # type: ignore[attr-defined]
            ptr = ctypes.windll.kernel32.GlobalLock(handle)  # type: ignore[attr-defined]
            ctypes.memmove(ptr, encoded, len(encoded))
            ctypes.windll.kernel32.GlobalUnlock(handle)  # type: ignore[attr-defined]
            ctypes.windll.user32.SetClipboardData(13, handle)  # type: ignore[attr-defined]
            return True
        except (OSError, ImportError, AttributeError) as _:
            return False
        finally:
            try:
                ctypes.windll.user32.CloseClipboard()  # type: ignore[attr-defined]
            except (OSError, AttributeError) as _:
                pass

    return False  # unsupported platform
