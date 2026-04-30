from src.utils.ui import console

BANNER_FULL = """\

  [bold indian_red]██████╗  ██████╗  ██████╗███████╗██████╗  █████╗ ████████╗ ██████╗██╗  ██╗[/bold indian_red]
  [bold indian_red]██╔══██╗██╔═══██╗██╔════╝██╔════╝██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██║  ██║[/bold indian_red]
  [bold indian_red]██║  ██║██║   ██║██║     ███████╗██████╔╝███████║   ██║   ██║     ███████║[/bold indian_red]
  [bold indian_red]██║  ██║██║   ██║██║     ╚════██║██╔═══╝ ██╔══██║   ██║   ██║     ██╔══██║[/bold indian_red]
  [bold indian_red]██████╔╝╚██████╔╝╚██████╗███████║██║     ██║  ██║   ██║   ╚██████╗██║  ██║[/bold indian_red]
  [bold indian_red]╚═════╝  ╚═════╝  ╚═════╝╚══════╝╚═╝     ╚═╝  ╚═╝   ╚═╝    ╚═════╝╚═╝  ╚═╝[/bold indian_red]

  [dim]  Auto-generate docstrings, READMEs, and changelogs from your git diff.[/dim]
  [dim]  Only what changed gets documented — BYOK · git-aware · v0.1.0[/dim]
  [dim]  Providers: Google Gemini · OpenAI · Anthropic   Run [/dim][bold dim]dp setup[/bold dim][dim] to start.[/dim]

"""

BANNER_INLINE = "  [bold indian_red]◈ docspatch[/bold indian_red]  [dim]v0.1.0  ·  docstrings · README · changelog · BYOK[/dim]\n"


def print_banner(full: bool = False) -> None:
    """Print the docspatch banner.

    Args:
        full (bool): Whether to print the full banner or an inline version."""
    console.print(BANNER_FULL if full else BANNER_INLINE)
