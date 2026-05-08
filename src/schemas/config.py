"""Configuration schemas for docspatch settings and provider keys."""

from pydantic import BaseModel, Field

__all__ = ["AppConfig", "AppDefaults", "AppKeys", "ProviderConfig"]


class AppDefaults(BaseModel):
    """User-configurable defaults persisted to config.toml."""

    style: str = "compact"
    scout_model: str = "gemini-2.5-flash-lite"
    writer_model: str = "gemini-2.5-pro"
    provider_key: str = "Google Gemini"
    batch_size: int = 5
    batch_max_lines: int = 500
    tokens_per_fn_compact: int = 50
    tokens_per_fn_detailed: int = 150
    large_threshold: int = 50
    diff_cap: int = 200
    log_count: int = 10
    prune_after_days: int = 30
    readme_tokens_compact: int = 2000
    readme_tokens_detailed: int = 5000
    changelog_diff_cap: int = 8000
    changelog_tokens: int = 1500


class AppKeys(BaseModel):
    """API keys — stored in config.toml, never in env or logs."""

    google_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None


class AppConfig(BaseModel):
    """Root config object; loaded once and cached per process."""

    defaults: AppDefaults = Field(default_factory=AppDefaults)
    keys: AppKeys = Field(default_factory=AppKeys)


class ProviderConfig(BaseModel):
    """One entry in the provider catalogue defining available models."""

    key_field: str
    scout_models: list[str]
    writer_models: list[str]
