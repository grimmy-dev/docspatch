"""Provider catalogue mapping provider names to available models and API key fields."""

from src.schemas.config import ProviderConfig

__all__ = ["CUSTOM", "PROVIDERS"]

PROVIDERS: dict[str, ProviderConfig] = {
    "Google Gemini": ProviderConfig(
        key_field="google_api_key",
        models=["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"],
        review_models=["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
    ),
    "OpenAI": ProviderConfig(
        key_field="openai_api_key",
        models=[
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-5-mini-2025-08-07",
            "gpt-5-nano-2025-08-07",
            "gpt-5-2025-08-07",
        ],
        review_models=[
            "gpt-5.4",
            "gpt-5.4-mini",
            "gpt-5.4-nano",
            "gpt-5-mini-2025-08-07",
            "gpt-5-nano-2025-08-07",
            "gpt-5-2025-08-07",
        ],
    ),
    "Anthropic": ProviderConfig(
        key_field="anthropic_api_key",
        models=["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-6"],
        review_models=[
            "claude-haiku-4-5-20251001",
            "claude-sonnet-4-6",
            "claude-opus-4-6",
        ],
    ),
}

CUSTOM = "↩  Enter custom model name"
