"""Nodes for generating and regenerating docstrings using LLMs."""

import asyncio

from src.graph.nodes.docstring.prompts import build_prompt, parse_response_fallback
from src.schemas.graph_io import BatchDocsUpdate, CollectBatchesUpdate, RerunDocsUpdate
from src.schemas.llm_outputs import BatchDocstringOutput
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.llm import acall_llm, is_cancelled
from src.utils.log import get_logger
from src.utils.prompts import DOCSTRING_SYSTEM

__all__ = ["collect_batches", "docwriter_rerun", "docwriter_single"]

logger = get_logger(__name__)


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
