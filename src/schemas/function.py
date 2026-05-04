"""Metadata schema for extracted Python functions and module docstrings."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

__all__ = ["FunctionMetadata", "make_fn_id"]


def make_fn_id(filepath: Path, name: str) -> str:
    """Generate a unique identifier for a function across the repository.

    Args:
        filepath: The path to the file containing the function.
        name: The name of the function.

    Returns:
        A unique identifier string in the format "filepath::name"."""
    return f"{filepath}::{name}"


class FunctionMetadata(BaseModel):
    """Extracted metadata for a single Python function, method, or module docstring.

    Source code is intentionally excluded to keep state size minimal.
    Nodes requiring source code must read it from disk using file_path and lines.
    """

    kind: Literal["function", "module"] = "function"
    name: str
    file_path: Path
    docstring: str | None = None
    start_line: int
    end_line: int
    signature: str
    body_hash: str
    is_significant: bool = False
