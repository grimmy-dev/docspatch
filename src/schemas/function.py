"""Metadata schema for extracted Python functions."""

from pathlib import Path

from pydantic import BaseModel


def make_fn_id(filepath: Path, name: str) -> str:
    """Generate a unique identifier for a function across the repository."""
    return f"{filepath}::{name}"


class FunctionMetadata(BaseModel):
    """
    Extracted metadata for a single Python function or method.

    Source code is intentionally excluded to keep state size minimal.
    Nodes requiring source code must read it from disk using file_path and lines.
    """

    name: str
    file_path: Path
    docstring: str | None = None
    start_line: int
    end_line: int
    signature: str
    body_hash: str
    is_significant: bool = False
