"""Shared test helpers — imported directly by test files that need them."""

from pathlib import Path

from src.schemas.function import FunctionMetadata, make_fn_id


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
