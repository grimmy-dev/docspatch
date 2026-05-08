"""significance node — filters to only functions worth documenting."""

from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import SignificantFunctionsUpdate
from src.schemas.state import DocpatchState
from src.utils.log import get_logger

__all__ = ["filter_significant", "significance"]

logger = get_logger(__name__)


def filter_significant(
    catalog: dict[str, FunctionMetadata],
) -> tuple[list[str], dict[str, FunctionMetadata]]:
    """Return (significant_ids, pruned_catalog) keeping only entries marked significant."""
    significant_ids = [fn_id for fn_id, fn in catalog.items() if fn.is_significant]
    pruned = {fn_id: catalog[fn_id] for fn_id in significant_ids}
    return significant_ids, pruned


def significance(state: DocpatchState) -> SignificantFunctionsUpdate:
    """Keep only significant functions and prune the catalog to save state space."""
    kept, pruned_catalog = filter_significant(state.catalog)
    skipped = len(state.catalog) - len(kept)
    logger.debug("significance: kept %d, skipped %d", len(kept), skipped)
    return {"significant_functions": kept, "catalog": pruned_catalog}
