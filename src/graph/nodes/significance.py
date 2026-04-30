"""significance node — filters to only functions worth documenting."""

from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import SignificantFunctionsUpdate
from src.schemas.state import DocpatchState
from src.utils.log import get_logger

logger = get_logger(__name__)


def significance(state: DocpatchState) -> SignificantFunctionsUpdate:
    """Keep only significant functions and prune the catalog to save state space."""
    kept: list[str] = []
    pruned_catalog: dict[str, FunctionMetadata] = {}

    for fn_id, fn in state.catalog.items():
        if fn.is_significant:
            kept.append(fn_id)
            pruned_catalog[fn_id] = fn

    skipped = len(state.catalog) - len(kept)
    logger.debug("significance: kept %d, skipped %d", len(kept), skipped)
    return {"significant_functions": kept, "catalog": pruned_catalog}
