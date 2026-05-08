"""Shared test helpers and fixtures."""

from pathlib import Path

import pytest

from src.schemas.function import FunctionMetadata, make_fn_id
from src.utils.config import reset_cache


@pytest.fixture(autouse=True)
def _reset_config_cache() -> None:
    """Prevent config cache bleed between tests."""
    reset_cache()


def make_fn(
    name: str,
    file_path: str = "src/foo.py",
    start_line: int = 1,
    end_line: int = 10,
    docstring: str | None = None,
    body_hash: str = "abc123",
    is_significant: bool = False,
) -> FunctionMetadata:
    return FunctionMetadata(
        name=name,
        file_path=Path(file_path),
        start_line=start_line,
        end_line=end_line,
        signature=f"def {name}():",
        docstring=docstring,
        body_hash=body_hash,
        is_significant=is_significant,
    )


def make_catalog(*fns: FunctionMetadata) -> tuple[list[str], dict[str, FunctionMetadata]]:
    catalog = {make_fn_id(fn.file_path, fn.name): fn for fn in fns}
    return list(catalog.keys()), catalog
