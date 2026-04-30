"""hash_check nodes — filter files and functions by comparing against cache."""

import hashlib
from pathlib import Path

from src.schemas.graph_io import ParsedFunctionsUpdate, ScannerUpdate
from src.schemas.state import DocpatchState
from src.utils.cache import get_file_hash, get_function_hash
from src.utils.log import get_logger

logger = get_logger(__name__)


def hash_file(path: Path) -> str | None:
    """Return SHA-256 hex digest of file contents; returns None on OSError."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def file_hash_check(state: DocpatchState) -> ScannerUpdate:
    """Keep only files whose content hash differs from the cached value."""
    changed: list[Path] = []
    for path in state.changed_files:
        current = hash_file(path)
        if current is None:
            continue
        if current != get_file_hash(path):
            changed.append(path)

    logger.debug("file_hash_check: %d changed / %d total", len(changed), len(state.changed_files))
    return {"changed_files": changed}


def function_hash_check(state: DocpatchState) -> ParsedFunctionsUpdate:
    """Mark each function significant when its body hash differs from cache."""
    updated_catalog = dict(state.catalog)
    changed_count = 0

    for fn_id, fn in updated_catalog.items():
        cached = get_function_hash(fn.file_path, fn.name)
        significant = state.update_all or (fn.body_hash != cached)

        if significant:
            changed_count += 1
            updated_catalog[fn_id] = fn.model_copy(update={"is_significant": True})

    logger.debug(
        "function_hash_check: %d significant / %d total",
        changed_count,
        len(updated_catalog),
    )
    return {"catalog": updated_catalog}
