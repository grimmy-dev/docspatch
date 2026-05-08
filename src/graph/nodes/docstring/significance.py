"""significance node — filters to only functions worth documenting."""

from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import SignificantFunctionsUpdate
from src.schemas.state import DocpatchState
from src.utils.log import get_logger

__all__ = ["filter_significant", "significance"]

logger = get_logger(__name__)

# Functions with a body this short or shorter are considered trivial.
# A trivial function that already has a docstring is skipped to avoid
# false-positive rewrites on update_all runs.
_TRIVIAL_BODY_LINES = 1


def _is_trivial(fn: FunctionMetadata) -> bool:
    return fn.end_line - fn.start_line <= _TRIVIAL_BODY_LINES


def filter_significant(
    catalog: dict[str, FunctionMetadata],
) -> tuple[list[str], dict[str, FunctionMetadata]]:
    """Return (significant_ids, pruned_catalog) keeping only entries worth documenting.

    Excludes trivial single-statement functions that already have a docstring
    to avoid false-positive rewrites on update_all runs.
    """
    significant_ids = [fn_id for fn_id, fn in catalog.items() if fn.is_significant and not (_is_trivial(fn) and fn.docstring)]
    pruned = {fn_id: catalog[fn_id] for fn_id in significant_ids}
    return significant_ids, pruned


def significance(state: DocpatchState) -> SignificantFunctionsUpdate:
    """Keep only significant functions and prune the catalog to save state space."""
    kept, pruned_catalog = filter_significant(state.catalog)
    skipped = len(state.catalog) - len(kept)
    logger.debug("significance: kept %d, skipped %d", len(kept), skipped)
    return {"significant_functions": kept, "catalog": pruned_catalog}
