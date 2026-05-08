"""clg_aggregator LangGraph node — wraps aggregator_node for the changelog pipeline."""

from src.graph.nodes.aggregator import aggregator_node
from src.schemas.changelog_io import ChangelogAggregatorUpdate
from src.schemas.changelog_state import ChangelogState
from src.utils.config import load
from src.utils.llm.caller import is_cancelled
from src.utils.log import get_logger

__all__ = ["clg_aggregator"]

logger = get_logger(__name__)


async def clg_aggregator(state: ChangelogState) -> ChangelogAggregatorUpdate:
    """Combine scout directory summaries into one unified context string."""
    if state.dry_run or is_cancelled():
        return {}
    if state.scout_output is None or not state.scout_output["grouped"]:
        return {}

    cfg = load()
    context = await aggregator_node(grouped=state.scout_output["grouped"], model_key=cfg.defaults.scout_model)
    logger.debug("clg_aggregator: context_len=%d", len(context))
    return {"aggregated_context": context}
