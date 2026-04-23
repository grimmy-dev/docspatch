import platform
import subprocess
from contextlib import contextmanager
from typing import Generator

from questionary import Style as QStyle
from rich.console import Console

console = Console()

Q_STYLE = QStyle(
    [
        ("qmark", "fg:#00d7ff bold"),
        ("question", "bold"),
        ("answer", "fg:#00d7ff bold"),
        ("pointer", "fg:#00d7ff bold"),
        ("highlighted", "fg:#00d7ff bold"),
        ("selected", "fg:#00d7ff"),
        ("separator", "fg:#555555"),
        ("instruction", "fg:#555555 italic"),
    ]
)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard. Returns True on success."""
    system = platform.system()
    if system == "Darwin":
        candidates = [["pbcopy"]]
    elif system == "Windows":
        candidates = [["clip"]]
    else:  # Linux / BSD
        candidates = [
            ["wl-copy"],  # Wayland
            ["xclip", "-selection", "clipboard"],  # X11
            ["xsel", "--clipboard", "--input"],  # X11 alt
        ]
    for cmd in candidates:
        try:
            subprocess.run(
                cmd, input=text.encode(), capture_output=True, timeout=5, check=True
            )
            return True
        except Exception:
            continue
    return False


def step(name: str, detail: str = "") -> None:
    """Print a success message with optional detail."""
    if detail:
        console.print(f"  [green]✓[/green]  {name:<20} [dim]{detail}[/dim]")
    else:
        console.print(f"  [green]✓[/green]  {name}")


def warn(msg: str) -> None:
    """Print a warning message."""
    console.print(f"  [yellow]![/yellow]  [dim]{msg}[/dim]")


def info(msg: str) -> None:
    """Print an informational message."""
    console.print(f"  [dim]{msg}[/dim]")


@contextmanager
def spinning(label: str) -> Generator[None, None, None]:
    """
    Display a spinning indicator with a label while a generator is running.
    """
    with console.status(f"  {label}...", spinner="dots", spinner_style="dim"):
        yield
