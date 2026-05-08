"""clg_aggregator LangGraph node — wraps aggregator_node for the changelog pipeline."""

from pathlib import Path

from src.graph.nodes.aggregator import aggregator_node
from src.schemas.changelog_io import ChangelogAggregatorUpdate
from src.schemas.changelog_state import ChangelogState
from src.utils.config import load
from src.utils.llm.caller import is_cancelled
from src.utils.log import get_logger
from src.utils.persistent_cache import ensure_gitignore, get_scope_dir, read_unified, write_unified

__all__ = ["clg_aggregator"]

logger = get_logger(__name__)

_CACHE_SUBDIR = Path(".docspatch") / "cache"


async def clg_aggregator(state: ChangelogState) -> ChangelogAggregatorUpdate:
    """Combine scout directory summaries into one unified context string.

    Uses persistent cache: skips LLM when all scout summaries were cache hits
    and a prior unified.gz exists. Writes unified.gz after each successful LLM call.
    """
    if state.dry_run or is_cancelled():
        return {}
    if state.scout_output is None or not state.scout_output["grouped"]:
        return {}

    cfg = load()
    scout = state.scout_output
    total = len(scout["summaries"])
    hits = scout["cache_hits"]

    root = state.repo_path or Path(".")
    scope_dir = get_scope_dir(root / _CACHE_SUBDIR, root, root)

    if total > 0 and hits == total:
        cached = read_unified(scope_dir)
        if cached is not None:
            logger.debug("clg_aggregator: all cache hits, returning unified.gz (%d chars)", len(cached))
            return {"aggregated_context": cached}

    existing_unified = read_unified(scope_dir)

    context = await aggregator_node(
        grouped=scout["grouped"],
        model_key=cfg.defaults.scout_model,
        existing_unified=existing_unified,
    )
    logger.debug("clg_aggregator: context_len=%d", len(context))

    if context:
        ensure_gitignore(root, prompt_fn=lambda _: "n")
        write_unified(scope_dir, context)

    return {"aggregated_context": context}
