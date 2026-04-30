"""Logging setup for docspatch."""

import logging
from logging.handlers import RotatingFileHandler

from src.constants import DOCSPATCH_DIR

_LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s — %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a logger under the docspatch hierarchy so records reach setup handlers."""
    return logging.getLogger(f"docspatch.{name}")


def setup_logging(debug: bool = False) -> None:
    """Configure the root docspatch logger exactly once.

    Always writes DEBUG+ to DOCSPATCH_DIR/docspatch.log (5 MB, 3 backups).
    Adds a Rich-formatted console handler when debug=True.
    """
    root = logging.getLogger("docspatch")
    if root.handlers:
        return
    root.setLevel(logging.DEBUG)
    root.propagate = False

    DOCSPATCH_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        DOCSPATCH_DIR / "docspatch.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
    )
    file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root.addHandler(file_handler)

    if debug:
        from rich.console import Console
        from rich.logging import RichHandler

        # stderr keeps debug logs off the spinner's stdout stream — no interleaving
        debug_console = Console(stderr=True, highlight=False)
        rich_handler = RichHandler(console=debug_console, rich_tracebacks=False, show_path=False)
        rich_handler.setLevel(logging.DEBUG)
        root.addHandler(rich_handler)
