from enum import Enum
from typing import Optional

import questionary
import typer
from rich.console import Console

from docspatch.utils.ui import Q_STYLE

app = typer.Typer(
    name="dp",
    help="docspatch — auto-generate and update code documentation",
    no_args_is_help=False,
    invoke_without_command=True,
)
console = Console()


@app.callback(invoke_without_command=True)
def show_help(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _print_banner(full=True)
        console.print(ctx.get_help())
        raise typer.Exit()


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

_BANNER_FULL = """\

  [bold cyan]██████╗  ██████╗  ██████╗███████╗██████╗  █████╗ ████████╗ ██████╗██╗  ██╗[/bold cyan]
  [bold cyan]██╔══██╗██╔═══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║  ██║[/bold cyan]
  [bold cyan]██║  ██║██║   ██║██║     ███████╗██████╔╝███████║   ██║   ██║     ███████║[/bold cyan]
  [bold cyan]██║  ██║██║   ██║██║     ╚════██║██╔═══╝ ██╔══██║   ██║   ██║     ██╔══██║[/bold cyan]
  [bold cyan]██████╔╝╚██████╔╝╚██████╗███████║██║     ██║  ██║   ██║   ╚██████╗██║  ██║[/bold cyan]
  [bold cyan]╚═════╝  ╚═════╝  ╚═════╝╚══════╝╚═╝     ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝[/bold cyan]

  [dim]  Auto-generate docstrings, READMEs, and changelogs from your git diff.[/dim]
  [dim]  Only what changed gets documented — BYOK · git-aware · v0.1.0[/dim]
  [dim]  Providers: Google Gemini · OpenAI · Anthropic   Run [/dim][bold dim]dp setup[/bold dim][dim] to start.[/dim]

"""

_BANNER_INLINE = "  [bold cyan]◈ docspatch[/bold cyan]  [dim]v0.1.0  ·  docstrings · README · changelog · BYOK[/dim]\n"


def _print_banner(full: bool = False) -> None:
    console.print(_BANNER_FULL if full else _BANNER_INLINE)


# ---------------------------------------------------------------------------
# Provider catalogue
# ---------------------------------------------------------------------------

_PROVIDERS: dict[str, dict] = {
    "Google Gemini": {
        "key_field": "google_api_key",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
        "review_models": [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
    },
    "OpenAI": {
        "key_field": "openai_api_key",
        "models": [
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-5-mini-2025-08-07",
            "gpt-5-nano-2025-08-07",
            "gpt-5-2025-08-07",
        ],
        "review_models": [
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-5-mini-2025-08-07",
            "gpt-5-nano-2025-08-07",
            "gpt-5-2025-08-07",
        ],
    },
    "Anthropic": {
        "key_field": "anthropic_api_key",
        "models": ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-7"],
        "review_models": [
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6",
            "claude-opus-4-7",
        ],
    },
}

_CUSTOM = "↩  Enter custom model name"


def _pick_model(label: str, choices: list[str]) -> str | None:
    """Select from list; '↩ Enter custom' falls back to text input. Returns None if cancelled."""
    opts = choices + [_CUSTOM]
    pick = questionary.select(label, choices=opts, style=Q_STYLE).ask()
    if pick is None:
        return None
    if pick == _CUSTOM:
        custom = questionary.text("  Model name:", style=Q_STYLE).ask()
        return custom.strip() or None
    return pick


def _current_provider_name(cfg: dict) -> str | None:
    """Return provider display name using stored provider_key, falling back to first found key."""
    provider_key: str | None = cfg.get("defaults", {}).get("provider_key")
    if provider_key:
        return next(
            (
                pname
                for pname, p in _PROVIDERS.items()
                if p["key_field"] == provider_key
            ),
            None,
        )
    keys = cfg.get("keys", {})
    return next(
        (pname for pname, p in _PROVIDERS.items() if keys.get(p["key_field"])),
        None,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


class Style(str, Enum):
    compact = "compact"
    detailed = "detailed"


_dry_run = typer.Option(False, "--dry-run", help="Estimate tokens/cost, no LLM calls")
_batch = typer.Option(False, "--batch", help="Force batch mode")


def _base_state(
    command: str,
    target_path: str = "",
    style: Optional[str] = None,
    dry_run: bool = False,
    force_batch: bool = False,
    is_init: bool = False,
    from_ref: str = "",
    to_ref: str = "",
) -> dict:
    from docspatch.utils.config import get

    effective_style = style or get("style") or "compact"
    return {
        "command": command,
        "target_path": target_path,
        "style": effective_style,
        "is_init": is_init,
        "from_ref": from_ref,
        "to_ref": to_ref,
        "files": [],
        "changed_files": [],
        "parsed_functions": [],
        "needs_batching": force_batch,
        "batch_strategy": "auto",
        "batches": [],
        "generated_docs": [],
        "accepted_docs": [],
        "skipped_docs": [],
        "feedback": {},
        "rerun_docs": [],
        "doc_coverage": {},
        "token_estimate": 0,
        "token_actual": 0,
        "dry_run": dry_run,
    }


def _interactive_model_switch() -> bool:
    """Offer model/provider switch after rate limit. Returns True if user switched."""
    from docspatch.utils.config import load, save

    console.print("\n  [yellow]Rate limit hit.[/yellow]  Switch model or provider?\n")
    action = questionary.select(
        "What to do:",
        choices=["Switch model", "Switch provider", "Quit"],
        instruction="(↑↓ navigate  ·  Enter select  ·  Esc cancel)",
        style=Q_STYLE,
    ).ask()

    if not action or action == "Quit":
        return False

    cfg = load()

    if action == "Switch model":
        provider_name = _current_provider_name(cfg)
        if not provider_name:
            console.print(
                "  [yellow]No provider configured.[/yellow]  Run [bold]dp setup[/bold] first."
            )
            return False
        pick = _pick_model("Select model:", _PROVIDERS[provider_name]["models"])
        if pick:
            cfg.setdefault("defaults", {})["model"] = pick
            save(cfg)
            console.print(f"  [green]✓[/green]  Model → {pick}")
            return True
    else:
        import getpass

        provider_name = questionary.select(
            "Provider:", choices=list(_PROVIDERS.keys()), style=Q_STYLE
        ).ask()
        if not provider_name:
            return False
        p = _PROVIDERS[provider_name]
        existing_key = cfg.get("keys", {}).get(p["key_field"])
        if existing_key:
            reuse = questionary.confirm(
                f"  Use stored {provider_name} key?", default=True, style=Q_STYLE
            ).ask()
            api_key = (
                existing_key if reuse else getpass.getpass("\n  New API key: ").strip()
            )
        else:
            api_key = getpass.getpass("\n  API key: ").strip()
        if not api_key:
            return False
        model = _pick_model("Select model:", p["models"])
        if not model:
            return False
        review_model = (
            _pick_model("Select review model:", p["review_models"])
            or p["review_models"][0]
        )
        defaults = cfg.setdefault("defaults", {})
        defaults["model"] = model
        defaults["review_model"] = review_model
        defaults["provider_key"] = p["key_field"]
        cfg.setdefault("keys", {})[p["key_field"]] = api_key
        save(cfg)
        console.print(
            f"  [green]✓[/green]  Provider → {provider_name}  Model → {model}"
        )
        return True

    return False


_MAX_RATE_LIMIT_RETRIES = 3


def _run(graph, state: dict) -> None:
    from docspatch.utils.errors import RateLimitError

    for attempt in range(_MAX_RATE_LIMIT_RETRIES):
        try:
            final = graph.invoke(state)
            if state.get("dry_run"):
                estimate = final.get("token_estimate", 0)
                cost = (estimate / 1_000_000) * 1.00
                console.print(
                    f"\n  [dim]Dry run — estimated tokens: {estimate:,}  (~${cost:.3f})[/dim]"
                )
            else:
                tokens = final.get("token_actual", 0)
                if tokens:
                    console.print(f"\n  [dim]Tokens used: {tokens:,}[/dim]")
            return
        except RateLimitError:
            switched = _interactive_model_switch()
            if not switched:
                raise typer.Exit(code=1)
            if attempt < _MAX_RATE_LIMIT_RETRIES - 1:
                console.print("\n  [dim]Re-running with new model…[/dim]\n")
            else:
                console.print("\n  [red]Rate limit. Max retries reached.[/red]")
                raise typer.Exit(code=1)
        except RuntimeError as e:
            console.print(f"\n  [red]Error:[/red] {e}")
            raise typer.Exit(code=1)
        except KeyboardInterrupt:
            console.print("\n  [yellow]Interrupted.[/yellow]")
            raise typer.Exit(code=130)


def _require_git() -> None:
    from docspatch.utils.git import is_git_repo

    if not is_git_repo():
        console.print("  [red]Error:[/red] Not inside a git repository.")
        raise typer.Exit(code=1)


def _require_api_key() -> None:
    from docspatch.utils.config import get_api_key

    if not get_api_key():
        console.print(
            "  [red]No API key configured.[/red]\n"
            "  Run [bold]dp setup[/bold] to get started, or edit [dim]~/.docspatch/config.toml[/dim] directly."
        )
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def setup() -> None:
    """Interactive first-time setup — choose provider, enter API key, set style."""
    import getpass
    from docspatch.utils.config import CONFIG_PATH, load, save

    provider_name = questionary.select(
        "Provider:",
        choices=list(_PROVIDERS.keys()),
        style=Q_STYLE,
    ).ask()

    if not provider_name:
        raise typer.Exit(code=1)

    p = _PROVIDERS[provider_name]

    api_key = getpass.getpass("\n  API key: ").strip()
    if not api_key:
        console.print("  [red]No key entered. Exiting.[/red]")
        raise typer.Exit(code=1)

    console.print()
    model = _pick_model("Model for docs:", p["models"]) or p["models"][0]
    review_model = (
        _pick_model("Model for review:", p["review_models"]) or p["review_models"][0]
    )

    style_pick = questionary.select(
        "Default style:",
        choices=[
            "compact  — one-sentence summary",
            "detailed — full Args/Returns/Raises",
        ],
        style=Q_STYLE,
    ).ask()
    style = (
        "detailed" if style_pick and style_pick.startswith("detailed") else "compact"
    )

    config = load()
    config.setdefault("defaults", {}).update(
        {
            "style": style,
            "model": model,
            "review_model": review_model,
            "provider_key": p["key_field"],
        }
    )
    config.setdefault("keys", {})[p["key_field"]] = api_key
    save(config)

    console.print(f"\n  [green]✓[/green]  Config saved to {CONFIG_PATH}")
    console.print("      Run [bold]dp docs[/bold] to start.\n")


@app.command()
def config(
    action: str = typer.Argument("show", help="show | set"),
    key: Optional[str] = typer.Argument(
        None, help="Key to set (e.g. style, model, google_api_key)"
    ),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
) -> None:
    """Show or update config.

    Examples:
      dp config show
      dp config set style detailed
      dp config set model           (interactive select)
      dp config set review_model    (interactive select)
      dp config set provider        (switch provider + reuse or update key)
    """
    from docspatch.utils.config import load, save

    cfg = load()

    if action == "show":
        console.print("\n  [bold]~/.docspatch/config.toml[/bold]\n")
        for section, entries in cfg.items():
            console.print(f"  [dim][{section}][/dim]")
            for k, v in entries.items():
                display = f"{str(v)[:4]}{'*' * 8}" if "key" in k else str(v)
                console.print(f"    {k} = {display}")
        console.print()
        return

    if action != "set" or not key:
        console.print("  Usage: dp config set <key> <value>  |  dp config set provider")
        raise typer.Exit(code=1)

    # Provider switch: full wizard (select provider → enter/reuse key → select models)
    if key == "provider":
        import getpass

        provider_name = questionary.select(
            "Provider:", choices=list(_PROVIDERS.keys()), style=Q_STYLE
        ).ask()
        if not provider_name:
            raise typer.Exit()
        p = _PROVIDERS[provider_name]
        existing_key = cfg.get("keys", {}).get(p["key_field"])
        if existing_key:
            reuse = questionary.confirm(
                f"  Use stored {provider_name} key?", default=True, style=Q_STYLE
            ).ask()
            api_key = (
                existing_key if reuse else getpass.getpass("\n  New API key: ").strip()
            )
        else:
            api_key = getpass.getpass("\n  API key: ").strip()
        if not api_key:
            console.print("  [red]No key entered.[/red]")
            raise typer.Exit(code=1)
        model = _pick_model("Model for docs:", p["models"]) or p["models"][0]
        review_model = (
            _pick_model("Model for review:", p["review_models"])
            or p["review_models"][0]
        )
        cfg.setdefault("keys", {})[p["key_field"]] = api_key
        defaults = cfg.setdefault("defaults", {})
        defaults["model"] = model
        defaults["review_model"] = review_model
        defaults["provider_key"] = p["key_field"]
        save(cfg)
        console.print(
            f"\n  [green]✓[/green]  Provider → {provider_name}  Model → {model}\n"
        )
        return

    # Interactive model selection when value not provided
    if key in ("model", "review_model") and value is None:
        provider_name = _current_provider_name(cfg)
        if not provider_name:
            console.print(
                "  [yellow]No provider configured.[/yellow]  Run [bold]dp setup[/bold] first."
            )
            raise typer.Exit(code=1)
        p = _PROVIDERS[provider_name]
        model_list = p["models"] if key == "model" else p["review_models"]
        value = _pick_model(f"Select {key}:", model_list)

        if not value:
            console.print("  [dim]Cancelled.[/dim]")
            raise typer.Exit()

    if value is None:
        console.print("  Usage: dp config set <key> <value>")
        raise typer.Exit(code=1)

    if "key" in key:
        cfg.setdefault("keys", {})[key] = value
    else:
        cfg.setdefault("defaults", {})[key] = value

    save(cfg)
    display = f"{value[:4]}****" if "key" in key else value
    console.print(f"  [green]✓[/green]  {key} = {display}")


@app.command()
def init(
    style: Optional[Style] = typer.Option(None, "--style", help="Output style"),
    dry_run: bool = _dry_run,
) -> None:
    """Cold start — scan repo, prioritize files by coverage."""
    _print_banner()
    _require_git()
    if not dry_run:
        _require_api_key()
    from docspatch.graph.graphs.init_graph import build

    state = _base_state(
        "init", style=style.value if style else None, dry_run=dry_run, is_init=True
    )
    _run(build(), state)


@app.command()
def docs(
    path: Optional[str] = typer.Argument(None, help="File or directory to document"),
    style: Optional[Style] = typer.Option(None, "--style", help="Output style"),
    dry_run: bool = _dry_run,
    batch: bool = _batch,
) -> None:
    """Generate or update in-file docstrings for changed functions."""
    _print_banner()
    _require_git()
    if not dry_run:
        _require_api_key()
    from docspatch.graph.graphs.docs_graph import build

    state = _base_state(
        "docs",
        target_path=path or "",
        style=style.value if style else None,
        dry_run=dry_run,
        force_batch=batch,
    )
    _run(build(), state)


@app.command()
def readme(
    path: Optional[str] = typer.Argument(None, help="Output path for README"),
    style: Optional[Style] = typer.Option(None, "--style", help="Output style"),
    dry_run: bool = _dry_run,
) -> None:
    """Generate or update README.md."""
    _print_banner()
    _require_git()
    if not dry_run:
        _require_api_key()
    from docspatch.graph.graphs.readme_graph import build

    state = _base_state(
        "readme",
        target_path=path or "README.md",
        style=style.value if style else None,
        dry_run=dry_run,
    )
    _run(build(), state)


@app.command()
def clg(
    style: Optional[Style] = typer.Option(None, "--style", help="Output style"),
    dry_run: bool = _dry_run,
    batch: bool = _batch,
    from_ref: Optional[str] = typer.Option(
        None, "--from", help="Start commit or tag (e.g. v1.0.0)"
    ),
    to_ref: Optional[str] = typer.Option(
        None, "--to", help="End commit or tag (default: HEAD)"
    ),
) -> None:
    """Generate changelog from git diff.

    Examples:
      dp clg                       # all uncommitted changes
      dp clg --from v1.0.0         # since v1.0.0 tag
      dp clg --from v1.0.0 --to v1.1.0  # between two releases
    """
    _print_banner()
    _require_git()
    if not dry_run:
        _require_api_key()
    from docspatch.graph.graphs.clg_graph import build

    state = _base_state(
        "clg",
        style=style.value if style else None,
        dry_run=dry_run,
        force_batch=batch,
        from_ref=from_ref or "",
        to_ref=to_ref or "",
    )
    _run(build(), state)


@app.command()
def review(
    path: Optional[str] = typer.Argument(None, help="File or directory to review"),
    style: Optional[Style] = typer.Option(None, "--style", help="Output style"),
    dry_run: bool = _dry_run,
) -> None:
    """Code quality feedback."""
    _print_banner()
    _require_git()
    if not dry_run:
        _require_api_key()
    from docspatch.graph.graphs.review_graph import build

    state = _base_state(
        "review",
        target_path=path or "",
        style=style.value if style else None,
        dry_run=dry_run,
    )
    _run(build(), state)


@app.command()
def cleanup(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation"),
) -> None:
    """Remove ~/.docspatch/ config and cache. Shows uninstall instructions."""
    import shutil
    from docspatch.utils.config import CONFIG_DIR

    if not CONFIG_DIR.exists():
        console.print("  [dim]~/.docspatch/ not found — nothing to remove.[/dim]")
    else:
        targets = list(CONFIG_DIR.iterdir())
        console.print("\n  Will remove:")
        for t in targets:
            console.print(f"    [dim]{t}[/dim]")
        console.print()

        if not yes:
            choice = input("  Proceed? [y/n]: ").strip().lower()
            if choice != "y":
                console.print("  [dim]Cancelled.[/dim]")
                raise typer.Exit()

        shutil.rmtree(CONFIG_DIR, ignore_errors=True)
        console.print("  [green]✓[/green]  ~/.docspatch/ removed.")

    console.print(
        "\n  To uninstall the package:\n    [bold]uv tool uninstall docspatch[/bold]\n"
    )
