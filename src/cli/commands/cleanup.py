"""cleanup command — delete local docspatch data interactively."""

import questionary

from src.utils.ui import Q_STYLE, cli_error_handler, info, step

__all__ = ["cleanup"]


@cli_error_handler
def cleanup() -> None:
    """Delete local docspatch data interactively."""
    from src.constants import DOCSPATCH_DIR

    if not DOCSPATCH_DIR.exists():
        info("Nothing to clean up.")
        return

    choices = [
        questionary.Choice("Checkpoints (SQLite DB history)", value="checkpoints.db"),
        questionary.Choice("Cache (File & Function hashes)", value="cache.json"),
        questionary.Choice("Logs", value="docspatch.log"),
        questionary.Choice("Config (API Keys & Settings)", value="config.toml"),
    ]

    selected = questionary.checkbox("Select data to remove (use Space to select):", choices=choices, style=Q_STYLE).ask()

    if not selected:
        info("No items selected. Cleanup cancelled.")
        return

    for item in selected:
        path = DOCSPATCH_DIR / item
        if path.exists():
            path.unlink()
            step(f"Deleted {item}")

    if not any(DOCSPATCH_DIR.iterdir()):
        DOCSPATCH_DIR.rmdir()
