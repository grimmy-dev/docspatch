"""Nodes for generating and regenerating docstrings using LLMs."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any, cast

from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import BatchDocsUpdate, CollectBatchesUpdate, RerunDocsUpdate
from src.schemas.llm_outputs import BatchDocstringOutput, DocstringOutput
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.llm import acall_llm, is_cancelled
from src.utils.log import get_logger
from src.utils.prompts import DOCSTRING_STYLE, DOCSTRING_SYSTEM

logger = get_logger(__name__)


def read_file_slices(file_path: Path, functions: list[FunctionMetadata]) -> dict[str, str]:
    """Read file once and extract slices for all requested functions."""
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


async def docwriter_single(state: DocpatchState) -> BatchDocsUpdate:
    """Generate docstrings for a single batch of functions."""
    st = DocpatchState.model_validate(state)
    if is_cancelled() or st.dry_run:
        return {"generated_docs": {}, "token_actual": 0}

    cfg = load()
    style = st.style
    system = DOCSTRING_SYSTEM.get(style, DOCSTRING_SYSTEM["compact"])
    tokens_per_fn = cfg.defaults.tokens_per_fn_compact if style == "compact" else cfg.defaults.tokens_per_fn_detailed
    prompt = build_prompt(st.current_batch, st.catalog, style, tokens_per_fn)
    batch_names = {st.catalog[fid].name for fid in st.current_batch}

    parsed, raw_text, tokens = await acall_llm(cfg.defaults.model, system, prompt, output_model=BatchDocstringOutput)
    items = (
        [i for i in parsed.items if i.name in batch_names and i.docstring.strip()]
        if parsed
        else parse_response_fallback(raw_text, batch_names)
    )

    generated_docs: dict[str, str] = {}
    for fid in st.current_batch:
        fn_name = st.catalog[fid].name
        result = next((r for r in items if r.name == fn_name), None)
        if result:
            generated_docs[fid] = result.docstring

    logger.debug("docwriter_single: %d results, %d tokens", len(items), tokens)
    return {"generated_docs": generated_docs, "token_actual": tokens}


def collect_batches(state: DocpatchState) -> CollectBatchesUpdate:
    """Consolidate all batch results. (State reducer handles the actual merge.)"""
    return {}


async def _process_rerun_batch(
    fid: str,
    state: DocpatchState,
    style: str,
    system: str,
    model_key: str,
    tokens_per_fn: int,
) -> tuple[str, str | None, int]:
    """Call LLM for a single rerun function; returns (fid, docstring | None, tokens)."""
    if is_cancelled():
        return fid, None, 0

    fn = state.catalog[fid]
    prompt = build_prompt([fid], state.catalog, style, tokens_per_fn)
    feedback = state.feedback.get(fid, "")
    if feedback:
        prompt += f"\n\nUSER FEEDBACK FOR REVISION:\n{feedback}\n\nAdjust the docstring to address this feedback."

    batch_names = {fn.name}
    parsed, raw_text, tokens = await acall_llm(model_key, system, prompt, output_model=BatchDocstringOutput)
    items = (
        [i for i in parsed.items if i.name == fn.name and i.docstring.strip()] if parsed else parse_response_fallback(raw_text, batch_names)
    )
    return fid, items[0].docstring if items else None, tokens


async def docwriter_rerun(state: DocpatchState) -> RerunDocsUpdate:
    """Regenerate docstrings for functions based on user feedback."""
    st = DocpatchState.model_validate(state)
    if is_cancelled() or st.dry_run:
        return {"generated_docs": {}, "token_actual": 0}

    cfg = load()
    style = st.style
    system = DOCSTRING_SYSTEM.get(style, DOCSTRING_SYSTEM["compact"])
    tokens_per_fn = cfg.defaults.tokens_per_fn_compact if style == "compact" else cfg.defaults.tokens_per_fn_detailed

    tasks = [_process_rerun_batch(fid, st, style, system, cfg.defaults.model, tokens_per_fn) for fid in st.rerun_docs]
    results = await asyncio.gather(*tasks)

    generated_docs: dict[str, str] = {}
    total_tokens = 0
    for fid, docstring, tokens in results:
        total_tokens += tokens
        if docstring:
            generated_docs[fid] = docstring

    logger.debug("docwriter_rerun: %d regenerated, %d tokens", len(generated_docs), total_tokens)
    return {"generated_docs": generated_docs, "token_actual": total_tokens}
