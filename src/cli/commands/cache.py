"""cache command group — manage the docspatch project cache."""

import shutil
from pathlib import Path

import typer

from src.utils.git.repo import get_root
from src.utils.persistent_cache import get_scope_dir

__all__ = ["cache_app"]

_CACHE_SUBDIR = Path(".docspatch") / "cache"

cache_app = typer.Typer(name="cache", help="Manage the docspatch project cache.")


@cache_app.command("clear")
def clear(
    scope: Path | None = typer.Option(None, "--scope", help="Delete only this target path's cache."),
) -> None:
    """Delete the project cache, or a single scope's cache with --scope."""
    try:
        repo_root = get_root()
        cache_root = repo_root / _CACHE_SUBDIR

        if scope is not None:
            scope_dir = get_scope_dir(cache_root, scope.resolve(), repo_root)
            _clear_scope(scope_dir, label=str(scope))
        else:
            _clear_all(cache_root)
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc


def _clear_scope(scope_dir: Path, *, label: str) -> None:
    if not scope_dir.exists():
        typer.echo(f"No cache found for {label}.")
        return
    typer.echo(f"Deleting cache for {label}: {scope_dir}")
    shutil.rmtree(scope_dir)
    typer.echo(f"Cache cleared for {label}.")


def _clear_all(cache_root: Path) -> None:
    if not cache_root.exists():
        typer.echo("No cache found.")
        return
    typer.echo(f"Deleting cache: {cache_root}")
    shutil.rmtree(cache_root)
    typer.echo("Cache cleared.")
