"""readme_llm node — generates or updates README content via LLM."""

from src.graph.nodes.readme.prompts import README_SYSTEM, build_readme_prompt
from src.schemas.readme_io import ReadmeLLMUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.config import load
from src.utils.llm.caller import acall_llm, is_cancelled
from src.utils.log import get_logger

logger = get_logger(__name__)


async def readme_llm(state: ReadmeState) -> ReadmeLLMUpdate:
    """Call the LLM to generate or update the README. Skips on dry_run."""
    if is_cancelled() or state.dry_run:
        return {"generated_readme": "", "token_actual": 0}

    cfg = load()
    max_tokens = cfg.defaults.readme_tokens_compact if state.style == "compact" else cfg.defaults.readme_tokens_detailed
    _, raw_text, tokens = await acall_llm(cfg.defaults.review_model, README_SYSTEM, build_readme_prompt(state), max_tokens=max_tokens)

    logger.debug("readme_llm: %d tokens, %d chars output", tokens, len(raw_text))
    return {"generated_readme": raw_text, "token_actual": tokens}
