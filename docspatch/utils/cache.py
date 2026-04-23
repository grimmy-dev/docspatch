import json
from pathlib import Path

CACHE_PATH = Path.home() / ".docspatch" / "cache.json"

_mem: dict | None = None


def _load() -> dict:
    global _mem
    if _mem is None:
        if not CACHE_PATH.exists():
            _mem = {}
        else:
            try:
                with CACHE_PATH.open() as f:
                    _mem = json.load(f)
            except (json.JSONDecodeError, OSError):
                _mem = {}
    return _mem


def load() -> dict:
    return _load()


def save(data: dict) -> None:
    global _mem
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w") as f:
        json.dump(data, f, indent=2)
    _mem = data


def get_file_hash(path: str) -> str | None:
    return _load().get("files", {}).get(path)


def get_function_hash(path: str, func_name: str) -> str | None:
    return _load().get("functions", {}).get(path, {}).get(func_name)


def set_file_hash(path: str, hash_val: str) -> None:
    data = _load()
    data.setdefault("files", {})[path] = hash_val
    save(data)


def set_function_hashes(path: str, hashes: dict[str, str]) -> None:
    data = _load()
    data.setdefault("functions", {})[path] = hashes
    save(data)


def set_file_and_function_hashes(
    path: str, file_hash: str, func_hashes: dict[str, str]
) -> None:
    data = _load()
    data.setdefault("files", {})[path] = file_hash
    data.setdefault("functions", {})[path] = func_hashes
    save(data)


def invalidate_file(path: str) -> None:
    data = _load()
    data.get("files", {}).pop(path, None)
    data.get("functions", {}).pop(path, None)
    save(data)
