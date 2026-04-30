"""File and function body-hash cache backed by DOCSPATCH_DIR/cache.json."""

import json
from pathlib import Path
from typing import TypedDict, cast

from src.constants import DOCSPATCH_DIR
from src.utils.log import get_logger

logger = get_logger(__name__)

CACHE_PATH = DOCSPATCH_DIR / "cache.json"


class CacheData(TypedDict):
    """Persisted hash state: file-level and function-level."""

    files: dict[str, str]
    functions: dict[str, dict[str, str]]


# In-memory singleton cache
mem: CacheData | None = None


def load() -> CacheData:
    """Load cache from disk.

    Returns:
        CacheData: Cache data, or empty structure if missing or invalid."""
    global mem
    if mem is not None:
        return mem

    if not CACHE_PATH.exists():
        mem = {"files": {}, "functions": {}}
        return mem

    try:
        raw = json.loads(CACHE_PATH.read_text())
        mem = {
            "files": cast(dict[str, str], raw.get("files") or {}),
            "functions": cast(dict[str, dict[str, str]], raw.get("functions") or {}),
        }
    except (json.JSONDecodeError, OSError) as _:
        logger.debug("Cache unreadable, starting fresh")
        mem = {"files": {}, "functions": {}}
    return mem


def save(data: CacheData) -> None:
    """Write cache to disk and update in-memory copy.

    Args:
        data (CacheData): The cache data to save."""
    global mem
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, indent=2))
    mem = data


def get_file_hash(path: Path) -> str | None:
    """Return stored file hash for path.

    Args:
        path (Path): The path to the file.

    Returns:
        str | None: The file hash, or None if not cached."""
    return load()["files"].get(str(path))


def get_function_hash(path: Path, func_name: str) -> str | None:
    """Return stored body hash for a function in a file.

    Args:
        path (Path): The path to the file.
        func_name (str): The name of the function.

    Returns:
        str | None: The function body hash, or None if not cached."""
    return load()["functions"].get(str(path), {}).get(func_name)


def set_file_and_function_hashes(path: Path, file_hash: str, func_hashes: dict[str, str]) -> None:
    """Update file and all function hashes for path then persist."""
    data = load()
    data["files"][str(path)] = file_hash
    data["functions"][str(path)] = func_hashes
    save(data)
