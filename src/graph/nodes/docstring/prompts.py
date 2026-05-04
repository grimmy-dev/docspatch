"""Pure prompt-building and response-parsing for docstring generation."""

import json
import re
from pathlib import Path
from typing import Any, cast

from src.schemas.function import FunctionMetadata
from src.schemas.llm_outputs import DocstringOutput
from src.utils.prompts import DOCSTRING_STYLE

__all__ = ["build_prompt", "parse_response_fallback", "read_file_slices"]


def read_file_slices(file_path: Path, functions: list[FunctionMetadata]) -> dict[str, str]:
    """Read file once and extract source slices for all requested functions."""
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {fn.name: "" for fn in functions}
    return {fn.name: "\n".join(lines[fn.start_line - 1 : fn.end_line]) for fn in functions}


def build_prompt(
    batch_ids: list[str],
    catalog: dict[str, FunctionMetadata],
    style: str,
    tokens_per_fn: int,
) -> str:
    """Create the LLM prompt for a batch of functions or a single module."""
    style_note = DOCSTRING_STYLE.get(style, DOCSTRING_STYLE["compact"])

    # Module-level docstring: minimal dedicated prompt
    if len(batch_ids) == 1 and catalog[batch_ids[0]].kind == "module":
        fn = catalog[batch_ids[0]]
        file_sigs = [f"  {meta.signature}" for meta in catalog.values() if meta.file_path == fn.file_path and meta.kind == "function"][:20]
        lines = [
            f"Style: {style_note} Module docstring: one concise line, up to {tokens_per_fn} tokens.",
            f"\nFile: {fn.file_path.name}",
        ]
        if file_sigs:
            lines.append("\nDefined in this file:\n" + "\n".join(file_sigs))
        if fn.docstring:
            lines.append(f"\nExisting docstring (update if needed):\n{fn.docstring}")
        lines.append('\nReturn JSON: [{"name": "__module__", "docstring": "..."}]')
        return "\n".join(lines)

    # Function docstrings: same-file context first
    batch_files = {catalog[fid].file_path for fid in batch_ids}
    batch_names = {catalog[fid].name for fid in batch_ids}

    same_file = [
        f"  {fn.signature}"
        for fn in catalog.values()
        if fn.name not in batch_names and fn.file_path in batch_files and fn.kind == "function"
    ]
    cross_file = [
        f"  {fn.signature}"
        for fn in catalog.values()
        if fn.name not in batch_names and fn.file_path not in batch_files and fn.kind == "function"
    ]
    context = "\n".join((same_file + cross_file)[:20])

    by_file: dict[Path, list[FunctionMetadata]] = {}
    for fid in batch_ids:
        fn = catalog[fid]
        if fn.kind == "function":
            by_file.setdefault(fn.file_path, []).append(fn)

    functions_text_parts = []
    for file_path, fns in by_file.items():
        slices = read_file_slices(file_path, fns)
        for fn in fns:
            functions_text_parts.append(f"Function: {fn.name}\n{slices[fn.name]}")

    functions_text = "\n\n".join(functions_text_parts)
    return (
        f"Style: {style_note} Each docstring: up to {tokens_per_fn} tokens per function if justified.\n\n"
        f"Related functions (signatures only — for context only, do not document these):\n{context}\n\n"
        f"Generate docstrings for:\n\n{functions_text}"
    )


def parse_response_fallback(text: str, batch_names: set[str]) -> list[DocstringOutput]:
    """Parse JSON docstrings from raw LLM text when structured output is unavailable."""
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        raw = cast(list[dict[str, Any]], json.loads(match.group()))
    except (json.JSONDecodeError, TypeError) as _:
        return []

    return [
        DocstringOutput(name=item.get("name", ""), docstring=item.get("docstring", "").strip())
        for item in raw
        if item.get("name") in batch_names and item.get("docstring", "").strip()
    ]
