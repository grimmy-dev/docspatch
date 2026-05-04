"""Application-wide path constants."""

from pathlib import Path

__all__ = ["DOCSPATCH_DIR"]

DOCSPATCH_DIR = Path.home() / ".docspatch"
