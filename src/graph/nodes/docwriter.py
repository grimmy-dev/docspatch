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


def build_symbol_table(fn_ids: list[str], catalog: dict[str, FunctionMetadata]) -> dict[str, str]:
    """Map function names to their signatures for LLM context."""
    return {catalog[fid].name: catalog[fid].signature for fid in fn_ids if fid in catalog}


def build_prompt(
    batch_ids: list[str],
    catalog: dict[str, FunctionMetadata],
    symbol_table: dict[str, str],
    style: str,
) -> str:
    """Create the LLM prompt for a batch of functions."""
    batch_names = {catalog[fid].name for fid in batch_ids}
    context_lines = [f"  {sig}" for name, sig in symbol_table.items() if name not in batch_names]
    context = "\n".join(context_lines[:20])
    style_note = DOCSTRING_STYLE.get(style, DOCSTRING_STYLE["compact"])

    by_file: dict[Path, list[FunctionMetadata]] = {}
    for fid in batch_ids:
        fn = catalog[fid]
        by_file.setdefault(fn.file_path, []).append(fn)

    functions_text_parts = []
    for file_path, fns in by_file.items():
        slices = read_file_slices(file_path, fns)
        for fn in fns:
            functions_text_parts.append(f"Function: {fn.name}\n{slices[fn.name]}")

    functions_text = "\n\n".join(functions_text_parts)
    return f"Style: {style_note}\n\nRelated functions (signatures only):\n{context}\n\nGenerate docstrings for:\n\n{functions_text}"


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
    symbol_table = build_symbol_table(list(st.catalog.keys()), st.catalog)
    prompt = build_prompt(st.current_batch, st.catalog, symbol_table, style)
    batch_names = {st.catalog[fid].name for fid in st.current_batch}

    parsed, raw_text, tokens = await acall_llm(cfg.defaults.model, system, prompt, output_model=BatchDocstringOutput)
    items = (
        [i for i in parsed.items if i.name in batch_names and i.docstring.strip()]
        if parsed
        else parse_response_fallback(raw_text, batch_names)
    )

    logger.debug("docwriter_single: %d results, %d tokens", len(items), tokens)

    generated_docs: dict[str, str] = {}
    for fid in st.current_batch:
        fn_name = st.catalog[fid].name
        result = next((r for r in items if r.name == fn_name), None)
        if result:
            generated_docs[fid] = result.docstring

    return {"generated_docs": generated_docs, "token_actual": tokens}


def collect_batches(state: DocpatchState) -> CollectBatchesUpdate:
    """Consolidate all batch results. (State reducer handles the actual merge)."""
    return {}


async def _process_rerun_batch(
    fid: str,
    st: DocpatchState,
    symbol_table: dict[str, str],
    style: str,
    system: str,
    model_key: str,
) -> tuple[str, str | None, int]:
    """Call LLM for a single rerun function; returns (fid, docstring | None, tokens)."""
    if is_cancelled():
        return fid, None, 0

    fn = st.catalog[fid]
    prompt = build_prompt([fid], st.catalog, symbol_table, style)
    feedback = st.feedback.get(fid, "")
    if feedback:
        prompt += f"\n\nUSER FEEDBACK FOR REVISION:\n{feedback}\n\nAdjust the docstring to address this feedback."

    parsed, raw_text, tokens = await acall_llm(model_key, system, prompt, output_model=BatchDocstringOutput)
    items = (
        [i for i in parsed.items if i.name == fn.name and i.docstring.strip()] if parsed else parse_response_fallback(raw_text, {fn.name})
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
    symbol_table = build_symbol_table(list(st.catalog.keys()), st.catalog)

    tasks = [_process_rerun_batch(fid, st, symbol_table, style, system, cfg.defaults.model) for fid in st.rerun_docs]
    results = await asyncio.gather(*tasks)

    generated_docs: dict[str, str] = {}
    total_tokens = 0
    for fid, docstring, tokens in results:
        total_tokens += tokens
        if docstring:
            generated_docs[fid] = docstring

    logger.debug("docwriter_rerun: %d regenerated, %d tokens", len(generated_docs), total_tokens)
    return {"generated_docs": generated_docs, "token_actual": total_tokens}
