"""LLM cancellation control and async call wrapper.

Shell layer — all network I/O lives here. Nodes call acall_llm only.
"""

import threading
from typing import Any, cast

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from src.utils._llm_providers import _max_tokens_kwarg, extract_text, extract_tokens, get_llm
from src.utils.errors import classify_llm_error
from src.utils.log import get_logger

__all__ = ["acall_llm", "get_llm", "is_cancelled", "request_cancel", "reset_cancel"]

logger = get_logger(__name__)

CANCEL_EVENT = threading.Event()


def request_cancel() -> None:
    """Signal all in-flight LLM calls to abort."""
    CANCEL_EVENT.set()


def reset_cancel() -> None:
    """Clear the cancellation flag before starting a new run."""
    CANCEL_EVENT.clear()


def is_cancelled() -> bool:
    """Return True when a cancellation has been requested."""
    return CANCEL_EVENT.is_set()


async def acall_llm[T: BaseModel](
    model_key: str,
    system: str,
    prompt: str,
    output_model: type[T] | None = None,
    max_tokens: int | None = None,
) -> tuple[T | None, str, int]:
    """Make an async LLM call, supporting structured or raw text output.

    Args:
        model_key: Identifier for the LLM to use.
        system: System prompt.
        prompt: User prompt.
        output_model: Pydantic model for structured output; falls back to raw text if unsupported.
        max_tokens: Cap on output tokens.

    Returns:
        (parsed_model | None, raw_text, token_count)

    Raises:
        LLMError: If an error occurs during the LLM call.
    """
    if is_cancelled():
        return None, "", 0

    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm(model_key)
    messages = [SystemMessage(content=system), HumanMessage(content=prompt)]
    logger.debug("acall_llm model=%s prompt_len=%d structured=%s", model_key, len(prompt), output_model is not None)

    try:
        if output_model is not None:
            try:
                structured_llm = llm.with_structured_output(output_model, include_raw=True)
                response = cast(dict[str, Any], await structured_llm.ainvoke(messages))
                raw_msg = cast(BaseMessage, response["raw"])
                tokens = extract_tokens(raw_msg)
                parsed = cast(T | None, response.get("parsed"))
                logger.debug("acall_llm structured tokens=%d parsed=%s", tokens, parsed is not None)
                return parsed, "", tokens
            except (NotImplementedError, AttributeError) as _:
                pass  # provider lacks structured output — fall through to raw call

        caller = llm.bind(**_max_tokens_kwarg(llm, max_tokens)) if max_tokens is not None else llm
        raw_msg = cast(BaseMessage, await caller.ainvoke(messages))
        tokens = extract_tokens(raw_msg)
        raw_text = extract_text(raw_msg.content)
        logger.debug("acall_llm raw tokens=%d", tokens)
        return None, raw_text, tokens

    except Exception as exc:
        raise classify_llm_error(exc) from None
