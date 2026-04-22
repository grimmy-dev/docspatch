from contextlib import contextmanager
from typing import Generator

from rich.console import Console

console = Console()


def step(name: str, detail: str = "") -> None:
    if detail:
        console.print(f"  [green]✓[/green]  {name:<20} [dim]{detail}[/dim]")
    else:
        console.print(f"  [green]✓[/green]  {name}")


def warn(msg: str) -> None:
    console.print(f"  [yellow]![/yellow]  [dim]{msg}[/dim]")


def info(msg: str) -> None:
    console.print(f"  [dim]{msg}[/dim]")


@contextmanager
def spinning(label: str) -> Generator[None, None, None]:
    with console.status(f"  {label}...", spinner="dots", spinner_style="dim"):
        yield
