"""Config file read/write with a module-level cache."""

import tomllib

import tomli_w

from src.constants import DOCSPATCH_DIR
from src.schemas.config import AppConfig
from src.utils.log import get_logger

logger = get_logger(__name__)

CONFIG_DIR = DOCSPATCH_DIR
CONFIG_PATH = CONFIG_DIR / "config.toml"
cached_config: AppConfig | None = None


def load() -> AppConfig:
    """Load config from disk; returns defaults when file is absent.

    Caches the result — repeated calls skip disk I/O.

    Raises:
        RuntimeError: If the TOML file is malformed."""
    global cached_config
    if cached_config is not None:
        return cached_config
    if not CONFIG_PATH.exists():
        logger.debug("Config file absent, using defaults")
        cached_config = AppConfig()
        return cached_config
    try:
        with open(CONFIG_PATH, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(f"Malformed config file: {exc}") from exc
    logger.debug("Config loaded from %s", CONFIG_PATH)
    cached_config = AppConfig.model_validate(data)
    return cached_config


def save(cfg: AppConfig) -> None:
    """Persist config to disk and invalidate the in-process cache."""
    global cached_config
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = cfg.model_dump(exclude_none=True)
    with open(CONFIG_PATH, "wb") as f:
        tomli_w.dump(data, f)
    logger.debug("Config saved to %s", CONFIG_PATH)
    cached_config = None


def get(key: str, section: str = "defaults") -> object:
    """Read one field from the config by section and key name.

    Args:
        key: The name of the key to retrieve.
        section: The section of the config to read from. Defaults to "defaults".

    Returns:
        The value of the key, or None if the section or key is not found."""
    cfg = load()
    section_obj: object = getattr(cfg, section, None)
    if section_obj is None:
        return None
    value: object = getattr(section_obj, key, None)
    return value


def get_api_key() -> tuple[str, str] | None:
    """Return (provider_name, api_key) respecting the default provider first.

    Assumes that the config file has been loaded.

    Returns:
        A tuple of (provider_name, api_key) or None if no API key is found."""
    cfg = load()
    keys = cfg.keys

    provider_key = cfg.defaults.provider_key
    if provider_key == "Google Gemini" and keys.google_api_key:
        return "google", keys.google_api_key
    if provider_key == "OpenAI" and keys.openai_api_key:
        return "openai", keys.openai_api_key
    if provider_key == "Anthropic" and keys.anthropic_api_key:
        return "anthropic", keys.anthropic_api_key

    candidates: list[tuple[str, str | None]] = [
        ("google", keys.google_api_key),
        ("openai", keys.openai_api_key),
        ("anthropic", keys.anthropic_api_key),
    ]
    for name, key in candidates:
        if key:
            return name, key
    return None
