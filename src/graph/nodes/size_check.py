"""size_check node — prompts when the repo is too large to batch cheaply."""

from typing import cast

from langgraph.types import interrupt

from src.schemas.graph_io import FilePickInterrupt, SizeCheckInterrupt, SizeCheckUpdate
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.log import get_logger

logger = get_logger(__name__)


def size_check(state: DocpatchState) -> SizeCheckUpdate:
    """Gate large runs behind a user prompt; always passes through on dry_run."""
    cfg = load()
    fn_ids = state.significant_functions
    n = len(fn_ids)

    output_per_fn = cfg.defaults.tokens_per_fn_compact if state.style == "compact" else cfg.defaults.tokens_per_fn_detailed
    estimate = sum((state.catalog[fid].end_line - state.catalog[fid].start_line + 1) * 10 + output_per_fn for fid in fn_ids)

    if state.dry_run:
        logger.debug("size_check: dry_run, passing %d functions through", n)
        return {"batch_strategy": "auto", "significant_functions": fn_ids}

    threshold = cfg.defaults.large_threshold
    logger.debug("size_check: %d functions, threshold=%d, estimate=%d tokens", n, threshold, estimate)
    if n <= threshold:
        return {"batch_strategy": "auto", "significant_functions": fn_ids}

    strategy = cast(
        str,
        interrupt(
            SizeCheckInterrupt(
                type="size_check",
                file_count=n,
                threshold=threshold,
                token_estimate=estimate,
            )
        ),
    )

    logger.debug("size_check: user chose strategy=%s", strategy)

    if strategy == "quit":
        return {"batch_strategy": "quit", "significant_functions": []}

    if strategy == "smart":
        filtered = [fid for fid in fn_ids if not state.catalog[fid].docstring]
        return {"batch_strategy": "smart", "significant_functions": filtered}

    if strategy == "pick":
        file_names = sorted({str(state.catalog[fid].file_path) for fid in fn_ids})
        chosen = cast(list[str], interrupt(FilePickInterrupt(type="file_pick", files=file_names)))
        chosen_set = set(chosen)
        filtered = [fid for fid in fn_ids if str(state.catalog[fid].file_path) in chosen_set]
        return {"batch_strategy": "pick", "significant_functions": filtered}

    return {"batch_strategy": "auto", "significant_functions": fn_ids}
