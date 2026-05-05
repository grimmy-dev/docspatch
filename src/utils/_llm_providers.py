"""LLM provider factory — creates BaseChatModel instances from config."""

import os
from collections.abc import Callable
from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage

from src.utils.config import load

__all__ = ["get_llm", "PROVIDER_MAP"]

PROVIDER_MAP: dict[str, str] = {
    "Google Gemini": "google_api_key",
    "OpenAI": "openai_api_key",
    "Anthropic": "anthropic_api_key",
}


def make_google(model: str, api_key: str) -> BaseChatModel:
    """Create a ChatGoogleGenerativeAI instance."""
    os.environ["GOOGLE_API_KEY"] = api_key
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model)


def make_openai(model: str, api_key: str) -> BaseChatModel:
    """Create a ChatOpenAI instance."""
    os.environ["OPENAI_API_KEY"] = api_key
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model)


def make_anthropic(model: str, api_key: str) -> BaseChatModel:
    """Create a ChatAnthropic instance."""
    os.environ["ANTHROPIC_API_KEY"] = api_key
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model)  # type: ignore[call-arg]


FACTORIES: dict[str, Callable[[str, str], BaseChatModel]] = {
    "Google Gemini": make_google,
    "OpenAI": make_openai,
    "Anthropic": make_anthropic,
}


def _max_tokens_kwarg(llm: BaseChatModel, n: int) -> dict[str, int]:
    """Return the provider-specific keyword argument for capping output tokens."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        if isinstance(llm, ChatGoogleGenerativeAI):
            return {"max_output_tokens": n}
    except ImportError:
        pass
    return {"max_tokens": n}


def get_llm(model_key: str) -> BaseChatModel:
    """Return a LangChain chat model for the given model key.

    Raises:
        RuntimeError: If no API key is configured or provider is unknown.
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
        return FACTORIES[provider_key](model_key, api_key)

    for name, field in PROVIDER_MAP.items():
        key: str | None = getattr(cfg.keys, field, None)
        if key:
            return FACTORIES[name](model_key, key)

    raise RuntimeError("No API key configured. Run `dp setup`.")


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
    """Extract the total token count from a LangChain BaseMessage."""
    usage = cast(dict[str, Any], getattr(response, "usage_metadata", None) or {})
    if usage:
        if "total_tokens" in usage:
            return int(usage["total_tokens"])
        return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))
    rm = cast(dict[str, Any], getattr(response, "response_metadata", None) or {})
    if "token_usage" in rm:
        return int(rm["token_usage"].get("total_tokens", 0))
    return int(rm.get("prompt_token_count", 0)) + int(rm.get("candidates_token_count", 0))
