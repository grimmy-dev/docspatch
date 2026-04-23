import os
from typing import Callable

from langchain_core.language_models import BaseChatModel

from docspatch.utils.config import load


def extract_text(content: str | list) -> str:
    """Extract text content from a string or a list of blocks."""
    if isinstance(content, str):
        return content
    return " ".join(
        block.get("text", "") if isinstance(block, dict) else str(block)
        for block in content
    )


def extract_tokens(response) -> int:
    """Extract the total number of tokens from a response object."""
    meta = getattr(response, "usage_metadata", None)
    if not meta:
        return 0
    return meta.get("total_tokens", 0) or (
        meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
    )


def _make_google(model: str, api_key: str) -> BaseChatModel:
    """Create and return a ChatGoogleGenerativeAI model instance."""
    os.environ["GOOGLE_API_KEY"] = api_key
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=model)


def _make_openai(model: str, api_key: str) -> BaseChatModel:
    """Create and return a ChatOpenAI model instance."""
    os.environ["OPENAI_API_KEY"] = api_key
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=model)


def _make_anthropic(model: str, api_key: str) -> BaseChatModel:
    """Create and return a ChatAnthropic model instance."""
    os.environ["ANTHROPIC_API_KEY"] = api_key
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(model=model)  # type: ignore[call-arg]


_PROVIDER_FACTORIES: dict[str, Callable[[str, str], BaseChatModel]] = {
    "google_api_key": _make_google,
    "openai_api_key": _make_openai,
    "anthropic_api_key": _make_anthropic,
}


def get_llm(model_key: str = "model") -> BaseChatModel:
    """Return configured LangChain chat model."""
    config = load()
    defaults: dict = config.get("defaults", {})
    model_name: str = defaults.get(model_key, "gemini-2.5-flash")
    keys: dict = config.get("keys", {})

    # Honor explicit provider selection (written by setup / config set provider)
    stored_key: str | None = defaults.get("provider_key")
    if stored_key and (api_key := keys.get(stored_key)):
        factory = _PROVIDER_FACTORIES.get(stored_key)
        if factory:
            return factory(model_name, api_key)

    # Backward-compat fallback: first configured key wins
    for key_field, factory in _PROVIDER_FACTORIES.items():
        if api_key := keys.get(key_field):
            return factory(model_name, api_key)

    raise RuntimeError(
        "No API key configured.\n"
        "Add google_api_key, openai_api_key, or anthropic_api_key to ~/.docspatch/config.toml"
    )
