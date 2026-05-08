"""Pure display functions for CLI output — no questionary, no I/O beyond console."""

from pathlib import Path

from rich.table import Table

from src.graph.nodes.changelog.prompts import CHANGELOG_SYSTEM
from src.graph.nodes.readme.prompts import README_SYSTEM
from src.schemas.changelog_state import ChangelogState
from src.schemas.function import FunctionMetadata
from src.schemas.readme_state import ReadmeState
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.ui import console, short_path


def print_dry_run_breakdown(state: DocpatchState) -> None:
    """Show per-file token breakdown for --dry-run.

    Args:
        state: The DocpatchState object containing information about the project."""
    cfg = load()
    style = state.style
    output_per_fn = cfg.defaults.tokens_per_fn_compact if style == "compact" else cfg.defaults.tokens_per_fn_detailed
    cost_per_m = 1.00

    by_file: dict[str, list[str]] = {}
    for fid in state.significant_functions:
        fn = state.catalog[fid]
        by_file.setdefault(str(fn.file_path), []).append(fid)

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("file", style="dim")
    table.add_column("fns", justify="right")
    table.add_column("~tokens", justify="right", style="sandy_brown")
    table.add_column("~cost", justify="right", style="dim")

    total_fns = 0
    total_tokens = 0
    for filepath, fids in sorted(by_file.items()):
        n = len(fids)
        t = sum((state.catalog[fid].end_line - state.catalog[fid].start_line + 1) * 10 + output_per_fn for fid in fids)
        total_fns += n
        total_tokens += t
        table.add_row(short_path(filepath), str(n), f"{t:,}", f"${(t / 1_000_000) * cost_per_m:.4f}")

    table.add_row("", "", "", "")
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{total_fns}[/bold]",
        f"[bold sandy_brown]{total_tokens:,}[/bold sandy_brown]",
        f"[bold]${(total_tokens / 1_000_000) * cost_per_m:.3f}[/bold]",
    )
    console.print("\n[bold]Dry Run Estimation[/bold]")
    console.print(table)
    console.print("[dim]Remove [bold]--dry-run[/bold] to apply docstrings.[/dim]")


def print_check_results(significant: list[str], catalog: dict[str, FunctionMetadata]) -> None:
    """Display table of functions that need documentation.

    Args:
        significant: A list of function IDs that are undocumented or have changed.
        catalog: A dictionary mapping function IDs to their metadata."""
    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("File", style="dim")
    table.add_column("Function", style="bold")
    table.add_column("Reason", style="yellow")

    for fid in significant:
        fn = catalog[fid]
        reason = "missing docstring" if not fn.docstring else "body changed"
        table.add_row(short_path(fn.file_path), fn.name, reason)

    console.print("\n[bold red]Undocumented or changed functions:[/bold red]")
    console.print(table)
    console.print(f"\n[red]{len(significant)} function(s) need documentation.[/red]")
    console.print("[dim]Run [bold]dp docs[/bold] to generate missing docstrings.[/dim]")


def print_readme_dry_run(state: ReadmeState, prompt: str) -> None:
    """Show context summary and token estimate for dp readme --dry-run.

    Args:
        state: The ReadmeState object containing information about the README generation.
        prompt: The prompt used for generating the README content."""
    cfg = load()
    input_tokens = (len(README_SYSTEM) + len(prompt)) // 4
    output_tokens = cfg.defaults.readme_tokens_compact if state.style == "compact" else cfg.defaults.readme_tokens_detailed
    cost_estimate = ((input_tokens + output_tokens) / 1_000_000) * 15.0
    token_var = "readme_tokens_compact" if state.style == "compact" else "readme_tokens_detailed"
    ctx = state.project_context
    fallback_name = Path(state.repo_path or state.target_path or ".").name
    project_name = ctx.name or fallback_name
    tree_lines = state.dir_tree.count("\n") + 1 if state.dir_tree else 0

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value", style="sandy_brown")

    name_ver = f"{project_name} {ctx.version or ''}".strip()
    table.add_row("Project", name_ver)
    table.add_row("Scope", short_path(str(state.target_path or state.repo_path or ".")))
    if ctx.description:
        table.add_row("Description", ctx.description[:80])
    if state.remote_url:
        table.add_row("Repository", state.remote_url)
    table.add_row("Dependencies", str(len(ctx.dependencies)))
    table.add_row("Dir tree", f"{tree_lines} entries" if tree_lines else "empty")
    table.add_row("Existing README", "yes" if state.existing_readme else "no")
    table.add_row("Mode", "rewrite" if state.rewrite else "update")
    table.add_row("Style", state.style)
    table.add_row("", "")
    table.add_row("~Input tokens", f"{input_tokens:,}")
    table.add_row(f"~Output cap ({token_var})", f"{output_tokens:,}")
    table.add_row("~Estimated cost", f"${cost_estimate:.4f}")

    console.print("\n[bold]Dry Run — dp readme[/bold]")
    console.print(table)
    console.print(f"\n[dim]Tune output length: dp config and edit {token_var}[/dim]")


def print_clg_dry_run(state: ChangelogState, prompt: str) -> None:
    """Show context summary and token estimate for dp clg --dry-run."""
    cfg = load()
    input_tokens = (len(CHANGELOG_SYSTEM) + len(prompt)) // 4
    output_tokens = cfg.defaults.changelog_tokens
    cost_estimate = ((input_tokens + output_tokens) / 1_000_000) * 15.0

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold")
    table.add_column("Value", style="sandy_brown")

    repo_name = Path(state.repo_path or ".").name
    table.add_row("Repository", repo_name)
    table.add_row("Version", state.version)
    if state.from_ref:
        end = state.to_ref or "HEAD"
        table.add_row("Range", f"{state.from_ref}..{end}")
    else:
        table.add_row("Range", "uncommitted working tree")
    table.add_row("Commits", str(len(state.commits)))
    table.add_row("Changed Python files", str(len(state.changed_files)))
    table.add_row("Breaking changes", "yes" if state.has_breaking_changes else "no")
    table.add_row("Initial commit", "yes" if state.is_initial_commit else "no")
    table.add_row("Style", state.style)
    table.add_row("", "")
    table.add_row("~Input tokens", f"{input_tokens:,}")
    table.add_row("~Output cap (changelog_tokens)", f"{output_tokens:,}")
    table.add_row("~Estimated cost", f"${cost_estimate:.4f}")

    console.print("\n[bold]Dry Run — dp clg[/bold]")
    console.print(table)
    console.print("\n[dim]Tune output length: dp config and edit changelog_tokens[/dim]")
