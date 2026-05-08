"""Scout persistent cache helpers — FileSummary serialisation, pre-load, and flush.

Bridge between persistent_cache (manifest / scope utilities) and the scout node
(FileSummary schema). No LangGraph, no LLM calls.
"""

import gzip
import json
import os
import time
from pathlib import Path

from src.schemas.scout_io import FileSummary
from src.utils.ast_compress import compress_file
from src.utils.fs import hash_content
from src.utils.persistent_cache import (
    Manifest,
    ManifestEntry,
    compute_cache_key,
    load_manifest,
    save_manifest,
)

__all__ = ["flush_persistent_results", "pre_load_persistent_hits"]

_SUMMARIES_NAME = "summaries.gz"


def _read_file_summaries(scope_dir: Path) -> dict[str, FileSummary]:
    """Load per-file summaries from scope directory; return empty dict if absent."""
    path = scope_dir / _SUMMARIES_NAME
    if not path.exists():
        return {}
    try:
        data: dict[str, FileSummary] = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
        return data
    except (OSError, gzip.BadGzipFile, EOFError, json.JSONDecodeError, KeyError) as _:
        return {}


def _write_file_summaries(scope_dir: Path, summaries: dict[str, FileSummary]) -> None:
    """Write per-file summaries atomically to scope directory."""
    scope_dir.mkdir(parents=True, exist_ok=True)
    tmp = scope_dir / f"{_SUMMARIES_NAME}.tmp"
    tmp.write_bytes(gzip.compress(json.dumps(summaries).encode("utf-8")))
    os.replace(tmp, scope_dir / _SUMMARIES_NAME)


def _rel_str(f: Path, repo_root: Path) -> str:
    try:
        return str(f.relative_to(repo_root))
    except ValueError:
        return f.name


def pre_load_persistent_hits(
    scope_dir: Path,
    files: list[Path],
    repo_root: Path,
    model_key: str,
    prompt_version: str,
) -> tuple[dict[str, FileSummary], list[tuple[str, str, str]], Manifest, dict[str, FileSummary]]:
    """Load manifest and summaries; pre-populate run_cache for persistent cache hits.

    Returns (hit_cache, all_file_data, manifest, file_summaries) where:
    - hit_cache: ast_hash → FileSummary for files whose cache key matches
    - all_file_data: (rel_path, ast_hash, cache_key) for every file in scope
    - manifest, file_summaries: existing on-disk state for flush_persistent_results
    """
    manifest = load_manifest(scope_dir)
    file_summaries = _read_file_summaries(scope_dir)
    key_to_path = {entry["key"]: path for path, entry in manifest.items()}

    hit_cache: dict[str, FileSummary] = {}
    all_file_data: list[tuple[str, str, str]] = []

    for f in files:
        rel = _rel_str(f, repo_root)
        skeleton = compress_file(f) or ""
        ast_hash = hash_content(skeleton)
        cache_key = compute_cache_key(ast_hash, model_key, prompt_version)
        all_file_data.append((rel, ast_hash, cache_key))

        cached_path = key_to_path.get(cache_key)
        if cached_path is not None and cached_path in file_summaries:
            hit_cache[ast_hash] = file_summaries[cached_path]

    return hit_cache, all_file_data, manifest, file_summaries


def flush_persistent_results(
    scope_dir: Path,
    all_file_data: list[tuple[str, str, str]],
    effective_cache: dict[str, FileSummary],
    manifest: Manifest,
    file_summaries: dict[str, FileSummary],
    ttl_days: int,
) -> None:
    """Write updated manifest and file summaries after a successful scout run."""
    expiry = time.time() + ttl_days * 86400
    new_manifest = dict(manifest)
    new_summaries = dict(file_summaries)

    for rel_path, ast_hash, cache_key in all_file_data:
        summary = effective_cache.get(ast_hash)
        if summary is not None:
            new_manifest[rel_path] = ManifestEntry(key=cache_key, expires_at=expiry)
            new_summaries[rel_path] = summary

    save_manifest(scope_dir, new_manifest)
    _write_file_summaries(scope_dir, new_summaries)
