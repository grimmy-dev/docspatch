"""batcher node — groups significant functions into LLM-sized batches."""

from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import BatcherUpdate
from src.schemas.state import DocpatchState
from src.utils.config import load
from src.utils.log import get_logger

__all__ = ["batcher", "group_batches"]

logger = get_logger(__name__)


def group_batches(fn_ids: list[str], catalog: dict[str, FunctionMetadata], batch_size: int, max_lines: int) -> list[list[str]]:
    """Group function IDs into batches, keeping same-file functions together.

    Sorts by size descending within each file for better bin-packing.
    Leftover incomplete batches from all files are merged and re-batched
    to avoid many single-function LLM calls.
    """
    if not fn_ids:
        return []

    by_file: dict[str, list[str]] = {}
    for fn_id in fn_ids:
        by_file.setdefault(str(catalog[fn_id].file_path), []).append(fn_id)

    batches: list[list[str]] = []

    for file_fns in by_file.values():
        file_fns.sort(key=lambda fid: catalog[fid].end_line - catalog[fid].start_line, reverse=True)
        current: list[str] = []
        current_lines = 0

        for fn_id in file_fns:
            fn = catalog[fn_id]
            lines = max(1, fn.end_line - fn.start_line)

            if current and (current_lines + lines > max_lines):
                batches.append(current)
                current = []
                current_lines = 0

            current.append(fn_id)
            current_lines += lines

            if len(current) >= batch_size:
                batches.append(current)
                current = []
                current_lines = 0

        if current:
            batches.append(current)

    return batches


def batcher(state: DocpatchState) -> BatcherUpdate:
    """Split significant_functions into batches ready for parallel docwriting."""
    if state.batch_strategy == "quit" or not state.significant_functions:
        return {"batches": [], "warnings": []}

    cfg = load()
    batch_size = cfg.defaults.batch_size
    max_lines = cfg.defaults.batch_max_lines
    diff_cap = cfg.defaults.diff_cap

    eligible: list[str] = []
    oversized: list[str] = []
    for fid in state.significant_functions:
        fn = state.catalog[fid]
        if fn.kind == "function" and (fn.end_line - fn.start_line) > diff_cap:
            oversized.append(fn.name)
        else:
            eligible.append(fid)

    warnings: list[str] = []
    if oversized:
        warnings.append(f"Skipped {len(oversized)} function(s) exceeding {diff_cap}-line cap: {', '.join(oversized)}")

    batches = group_batches(eligible, state.catalog, batch_size, max_lines)
    logger.debug("batcher: %d batches, %d functions (%d skipped)", len(batches), len(eligible), len(oversized))
    return {"batches": batches, "warnings": warnings}
