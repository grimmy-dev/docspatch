"""readme_aggregator LangGraph node — wraps aggregator_node for the README pipeline."""

from pathlib import Path

from src.graph.nodes.aggregator import aggregator_node
from src.schemas.readme_io import ReadmeAggregatorUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.config import load
from src.utils.llm.caller import is_cancelled
from src.utils.log import get_logger
from src.utils.persistent_cache import ensure_gitignore, get_scope_dir, read_unified, write_unified

__all__ = ["readme_aggregator"]

logger = get_logger(__name__)

_CACHE_SUBDIR = Path(".docspatch") / "cache"


async def readme_aggregator(state: ReadmeState) -> ReadmeAggregatorUpdate:
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

    scope_dir: Path | None = None
    if state.repo_root is not None:
        target = Path(state.target_path).resolve() if state.target_path is not None else state.repo_root
        root = state.repo_root
        scope_dir = get_scope_dir(root / _CACHE_SUBDIR, target, root)

    if scope_dir is not None and total > 0 and hits == total:
        cached = read_unified(scope_dir)
        if cached is not None:
            logger.debug("readme_aggregator: all cache hits, returning unified.gz (%d chars)", len(cached))
            return {"aggregated_context": cached}

    existing_unified: str | None = read_unified(scope_dir) if scope_dir is not None else None

    context = await aggregator_node(
        grouped=scout["grouped"],
        model_key=cfg.defaults.scout_model,
        existing_unified=existing_unified,
    )
    logger.debug("readme_aggregator: context_len=%d", len(context))

    if scope_dir is not None and context:
        if state.repo_root is not None:
            ensure_gitignore(state.repo_root, prompt_fn=lambda _: "n")
        write_unified(scope_dir, context)

    return {"aggregated_context": context}
