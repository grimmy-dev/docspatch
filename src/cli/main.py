"""docspatch CLI — app wiring only."""

import typer

from src.cli import commands
from src.cli.banner import print_banner
from src.cli.commands.cache import cache_app
from src.utils.log import get_logger, setup_logging
from src.utils.ui import console

logger = get_logger(__name__)

app = typer.Typer(
    name="dp",
    help="docspatch — auto-generate and update code documentation",
    no_args_is_help=False,
    invoke_without_command=True,
)

app.add_typer(cache_app, name="cache")
app.command()(commands.docs)
app.command()(commands.setup)
app.command()(commands.config)
app.command()(commands.cleanup)
app.command()(commands.readme)
app.command()(commands.clg)
app.command()(commands.review)
app.command()(commands.init)


@app.callback(invoke_without_command=True)
def show_help(
    ctx: typer.Context,
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
) -> None:
    """Display help or delegate to a subcommand.

    Args:
        ctx: Typer context.
        debug: Enable debug logging."""
    setup_logging(debug=debug)
    logger.debug("docspatch starting")
    if ctx.invoked_subcommand is None:
        print_banner(full=True)
        console.print(ctx.get_help())
        raise typer.Exit()
