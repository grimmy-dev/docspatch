"""Pure prompt-building for docstring generation.

CORE layer — no I/O. Callers supply pre-read file slices via the
file_slices parameter so this module has no disk dependencies.
"""

from pathlib import Path

from src.schemas.function import FunctionMetadata
from src.utils.llm.prompts import DOCSTRING_STYLE

__all__ = ["build_prompt"]


def build_prompt(
    batch_ids: list[str],
    catalog: dict[str, FunctionMetadata],
    style: str,
    tokens_per_fn: int,
    file_slices: dict[Path, dict[str, str]],
) -> str:
    """Create the LLM prompt for a batch of functions or a single module.

    file_slices maps each file path to a dict of {function_name: source_slice}.
    For module-level prompts the mapping is not consulted.
    """
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

    same_file: list[str] = []
    cross_file: list[str] = []
    for fn in catalog.values():
        if fn.name in batch_names or fn.kind != "function":
            continue
        (same_file if fn.file_path in batch_files else cross_file).append(f"  {fn.signature}")
    context = "\n".join((same_file + cross_file)[:20])

    by_file: dict[Path, list[FunctionMetadata]] = {}
    for fid in batch_ids:
        fn = catalog[fid]
        if fn.kind == "function":
            by_file.setdefault(fn.file_path, []).append(fn)

    functions_text_parts = []
    for file_path, fns in by_file.items():
        slices = file_slices.get(file_path, {})
        for fn in fns:
            functions_text_parts.append(f"Function: {fn.name}\n{slices.get(fn.name, '')}")

    functions_text = "\n\n".join(functions_text_parts)
    return (
        f"Style: {style_note} Each docstring: up to {tokens_per_fn} tokens per function if justified.\n\n"
        f"Related functions (signatures only — for context only, do not document these):\n{context}\n\n"
        f"Generate docstrings for:\n\n{functions_text}"
    )
