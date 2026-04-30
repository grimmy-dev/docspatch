"""LLM factory, cancellation control, and call wrappers.

Shell layer — all network I/O lives here. Nodes call acall_llm only.
"""

import os
import threading
from collections.abc import Callable
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from src.utils.config import load
from src.utils.errors import classify_llm_error
from src.utils.log import get_logger

logger = get_logger(__name__)

CANCEL_EVENT = threading.Event()

PROVIDER_MAP: dict[str, str] = {
    "Google Gemini": "google_api_key",
    "OpenAI": "openai_api_key",
    "Anthropic": "anthropic_api_key",
}


def request_cancel() -> None:
    """Signal all in-flight LLM calls to abort."""
    CANCEL_EVENT.set()


def reset_cancel() -> None:
    """Clear the cancellation flag before starting a new run."""
    CANCEL_EVENT.clear()


def is_cancelled() -> bool:
    """Return True when a cancellation has been requested."""
    return CANCEL_EVENT.is_set()


def extract_text(content: str | list[str | dict[str, object]]) -> str:
    """Pull plain text from a string or list of content blocks."""
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif hasattr(block, "text"):
            parts.append(str(block.text))
    return "".join(parts)


def extract_tokens(response: BaseMessage) -> int:
    """Extract token count from an AIMessage; returns 0 when unavailable.

    Check order: total_tokens → input+output → Gemini prompt+candidates.
    """
    usage = getattr(response, "usage_metadata", None) or {}
    if usage:
        if "total_tokens" in usage:
            return int(usage["total_tokens"])
        return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
    rm = getattr(response, "response_metadata", None) or {}
    if "token_usage" in rm:
        return int(rm["token_usage"].get("total_tokens", 0))
    return int(rm.get("prompt_token_count", 0)) + int(rm.get("candidates_token_count", 0))


def make_google(model: str, api_key: str) -> BaseChatModel:
    """Create a ChatGoogleGenerativeAI instance; key set via env var."""
    os.environ["GOOGLE_API_KEY"] = api_key
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model)


def make_openai(model: str, api_key: str) -> BaseChatModel:
    """Create a ChatOpenAI instance; key set via env var."""
    os.environ["OPENAI_API_KEY"] = api_key
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model)


def make_anthropic(model: str, api_key: str) -> BaseChatModel:
    """Create a ChatAnthropic instance; key set via env var."""
    os.environ["ANTHROPIC_API_KEY"] = api_key
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model)  # type: ignore[call-arg]


FACTORIES: dict[str, Callable[[str, str], BaseChatModel]] = {
    "Google Gemini": make_google,
    "OpenAI": make_openai,
    "Anthropic": make_anthropic,
}


def get_llm(model_key: str) -> BaseChatModel:
    """Return a LangChain chat model using the configured provider.

    Raises RuntimeError immediately when provider_key is set but API key is missing.
    When no provider_key is set, iterates all configured keys.
    """
    cfg = load()
    provider_key = cfg.defaults.provider_key

    if provider_key:
        key_field = PROVIDER_MAP.get(provider_key)
        if key_field is None:
            raise RuntimeError(f"Unknown provider: {provider_key}. Run `dp setup`.")
        api_key: str | None = getattr(cfg.keys, key_field, None)
        if not api_key:
            raise RuntimeError(f"API key for '{provider_key}' not set. Run `dp setup`.")
        factory = FACTORIES[provider_key]
        return factory(model_key, api_key)

    for name, field in PROVIDER_MAP.items():
        key: str | None = getattr(cfg.keys, field, None)
        if key:
            return FACTORIES[name](model_key, key)

    raise RuntimeError("No API key configured. Run `dp setup`.")


async def acall_llm[T: BaseModel](
    model_key: str,
    system: str,
    prompt: str,
    output_model: type[T] | None = None,
) -> tuple[T | None, str, int]:
    """Async LLM call used by all async graph nodes.

    When output_model is provided, attempts structured output via with_structured_output.
    Returns (parsed, "", tokens) on structured success.
    Returns (None, raw_text, tokens) on fallback or when output_model is None.
    Returns (None, "", 0) when cancelled.
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

        raw_msg = await llm.ainvoke(messages)
        tokens = extract_tokens(raw_msg)
        raw_text = extract_text(raw_msg.content)
        logger.debug("acall_llm raw tokens=%d", tokens)
        return None, raw_text, tokens

    except Exception as exc:
        raise classify_llm_error(exc) from None
