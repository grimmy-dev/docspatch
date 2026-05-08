"""Pure prompt-building for docstring generation.

CORE layer — no I/O. Callers supply pre-read file slices via the
file_slices parameter so this module has no disk dependencies.
"""

from pathlib import Path

from src.schemas.function import FunctionMetadata

__all__ = ["DOCSTRING_STYLE", "DOCSTRING_SYSTEM", "build_prompt"]

DOCSTRING_SYSTEM: dict[str, str] = {
    "compact": (
        "You are a technical documentation expert. Write Google-style Python docstrings.\n"
        "Focus on PURPOSE and CONTRACT — why this exists, what the caller receives, what assumptions must hold.\n"
        "Rules: imperative voice ('Return X', not 'Returns X'); no implementation walkthrough; "
        "no filler prose; document Args and Returns only when non-trivial."
    ),
    "detailed": (
        "You are a technical documentation expert. Write Google-style Python docstrings.\n"
        "Focus on PURPOSE and CONTRACT — why this exists, what the caller receives, what edge cases apply.\n"
        "Rules: imperative voice ('Return X', not 'Returns X'); include Args, Returns, Raises, and Example "
        "where genuinely useful; document non-obvious invariants and constraints; no implementation walkthrough; "
        "no filler prose."
    ),
}

DOCSTRING_STYLE: dict[str, str] = {
    "compact": "One-line summary only. Args and Returns only if non-trivial. No examples.",
    "detailed": "Full docstring: summary, extended description if needed, Args, Returns, Raises, and Example sections where useful.",
}


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
    for fn in catalog.values():
        if fn.name in batch_names or fn.kind != "function":
            continue
        if fn.file_path in batch_files:
            same_file.append(f"  {fn.signature}")
    context = "\n".join(same_file[:10])

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
