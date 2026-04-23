import tomllib
import tomli_w
from pathlib import Path

CONFIG_DIR = Path.home() / ".docspatch"
CONFIG_PATH = CONFIG_DIR / "config.toml"

_DEFAULTS: dict = {
    "defaults": {
        "style": "compact",
        "model": "gemini-2.5-flash",
        "review_model": "gemini-2.5-pro",
    },
    "keys": {},
}


def load() -> dict:
    """Load configuration from file or return defaults."""
    if not CONFIG_PATH.exists():
        return _DEFAULTS.copy()
    try:
        with CONFIG_PATH.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise RuntimeError(f"Malformed config at {CONFIG_PATH}: {e}") from e


def save(config: dict) -> None:
    """Save configuration dictionary to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("wb") as f:
        tomli_w.dump(config, f)


def get(key: str, section: str = "defaults") -> str | None:
    """Get a configuration value by key and optional section."""
    config = load()
    return config.get(section, {}).get(key)


def set_value(key: str, value: str, section: str = "defaults") -> None:
    """
    Set a configuration value by key and optional section, saving the config.
    """
    config = load()
    config.setdefault(section, {})[key] = value
    save(config)


def get_api_key() -> tuple[str, str] | None:
    """Return (provider, key) for first configured provider, else None."""
    keys = load().get("keys", {})
    for provider, env_key in [
        ("google", "google_api_key"),
        ("openai", "openai_api_key"),
        ("anthropic", "anthropic_api_key"),
    ]:
        if value := keys.get(env_key):
            return provider, value
    return None


def require_api_key() -> tuple[str, str]:
    """
    Return (provider, key) for first configured provider, raising an error if none is found.
    """
    result = get_api_key()
    if result is None:
        raise RuntimeError(
            "No API key configured. Add one to ~/.docspatch/config.toml\n"
            "See config.toml.example for format."
        )
    return result
