"""clg_llm node — generates changelog entry via LLM."""

from src.graph.nodes.changelog.prompts import build_clg_prompt
from src.schemas.changelog_io import ChangelogLLMUpdate
from src.schemas.changelog_state import ChangelogState
from src.utils.config import load
from src.utils.llm.caller import acall_llm, is_cancelled
from src.utils.llm.prompts import CHANGELOG_SYSTEM
from src.utils.log import get_logger

__all__ = ["clg_llm"]

logger = get_logger(__name__)


async def clg_llm(state: ChangelogState) -> ChangelogLLMUpdate:
    """Call the LLM to generate a changelog entry. Skips on dry_run or nothing_to_document."""
    if is_cancelled() or state.dry_run or state.nothing_to_document:
        return {"generated_entry": "", "token_actual": 0}

    cfg = load()
    _, raw_text, tokens = await acall_llm(
        cfg.defaults.review_model,
        CHANGELOG_SYSTEM,
        build_clg_prompt(state),
        max_tokens=cfg.defaults.changelog_tokens,
    )
    logger.debug("clg_llm: %d tokens, %d chars output", tokens, len(raw_text))
    return {"generated_entry": raw_text, "token_actual": tokens}
