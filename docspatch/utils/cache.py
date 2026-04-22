import json
from pathlib import Path

CACHE_PATH = Path.home() / ".docspatch" / "cache.json"


def load() -> dict:
    if not CACHE_PATH.exists():
        return {}
    with CACHE_PATH.open() as f:
        return json.load(f)


def save(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w") as f:
        json.dump(cache, f, indent=2)


def get_file_hash(path: str) -> str | None:
    return load().get("files", {}).get(path)


def get_function_hash(path: str, func_name: str) -> str | None:
    return load().get("functions", {}).get(path, {}).get(func_name)


def set_file_hash(path: str, hash_val: str) -> None:
    cache = load()
    cache.setdefault("files", {})[path] = hash_val
    save(cache)


def set_function_hashes(path: str, hashes: dict[str, str]) -> None:
    cache = load()
    cache.setdefault("functions", {})[path] = hashes
    save(cache)


def invalidate_file(path: str) -> None:
    cache = load()
    cache.get("files", {}).pop(path, None)
    cache.get("functions", {}).pop(path, None)
    save(cache)
