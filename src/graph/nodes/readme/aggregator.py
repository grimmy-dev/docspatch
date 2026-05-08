"""readme_aggregator LangGraph node — wraps aggregator_node for the README pipeline."""

from src.graph.nodes.aggregator import aggregator_node
from src.schemas.readme_io import ReadmeAggregatorUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.config import load
from src.utils.llm.caller import is_cancelled
from src.utils.log import get_logger

__all__ = ["readme_aggregator"]

logger = get_logger(__name__)


async def readme_aggregator(state: ReadmeState) -> ReadmeAggregatorUpdate:
    """Combine scout directory summaries into one unified context string."""
    if state.dry_run or is_cancelled():
        return {}
    if state.scout_output is None or not state.scout_output["grouped"]:
        return {}

    cfg = load()
    context = await aggregator_node(grouped=state.scout_output["grouped"], model_key=cfg.defaults.model)
    logger.debug("readme_aggregator: context_len=%d", len(context))
    return {"aggregated_context": context}
