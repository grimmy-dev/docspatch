"""persistent_cache — pure core utilities for the .docspatch project cache.

No LangGraph, no LLM calls. Handles manifest read/write, unified context
gzip round-trip, cache key computation, TTL pruning, and .gitignore management.

Cache layout on disk:
    .docspatch/
      cache/
        <scope_hash>/
          manifest.json    # {path: {key, expires_at}}
          unified.gz       # gzip-compressed unified context string
"""

import gzip
import hashlib
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

__all__ = [
    "ManifestEntry",
    "Manifest",
    "compute_cache_key",
    "ensure_gitignore",
    "get_scope_dir",
    "get_scope_hash",
    "load_manifest",
    "prune_expired",
    "read_unified",
    "save_manifest",
    "write_unified",
]

_MANIFEST_NAME = "manifest.json"
_UNIFIED_NAME = "unified.gz"
_GITIGNORE_ENTRY = ".docspatch"


class ManifestEntry(TypedDict):
    """Cached metadata for a single file in the scope manifest."""

    key: str
    expires_at: float


Manifest = dict[str, ManifestEntry]


def compute_cache_key(ast_hash: str, model_name: str, prompt_version: str) -> str:
    """Deterministic cache key: sha256(ast_hash | model_name | prompt_version)."""
    raw = f"{ast_hash}|{model_name}|{prompt_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get_scope_hash(target_path: Path, repo_root: Path) -> str:
    """16-char hex hash of target_path relative to repo_root."""
    rel = str(target_path.relative_to(repo_root))
    return hashlib.sha256(rel.encode()).hexdigest()[:16]


def get_scope_dir(cache_root: Path, target_path: Path, repo_root: Path) -> Path:
    """Return the scope directory for the given target path."""
    return cache_root / get_scope_hash(target_path, repo_root)


def load_manifest(scope_dir: Path) -> Manifest:
    """Load manifest from scope directory; return empty dict if absent or corrupt."""
    path = scope_dir / _MANIFEST_NAME
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(k): ManifestEntry(key=v["key"], expires_at=float(v["expires_at"])) for k, v in data.items()}
    except json.JSONDecodeError, OSError, KeyError, TypeError:
        return {}


def save_manifest(scope_dir: Path, manifest: Manifest) -> None:
    """Write manifest atomically to scope directory."""
    scope_dir.mkdir(parents=True, exist_ok=True)
    tmp = scope_dir / f"{_MANIFEST_NAME}.tmp"
    tmp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    os.replace(tmp, scope_dir / _MANIFEST_NAME)


def read_unified(scope_dir: Path) -> str | None:
    """Decompress and return unified context; None if absent or corrupt."""
    path = scope_dir / _UNIFIED_NAME
    if not path.exists():
        return None
    try:
        return gzip.decompress(path.read_bytes()).decode("utf-8")
    except OSError, gzip.BadGzipFile, EOFError:
        return None


def write_unified(scope_dir: Path, content: str) -> None:
    """Compress and write unified context atomically."""
    scope_dir.mkdir(parents=True, exist_ok=True)
    tmp = scope_dir / f"{_UNIFIED_NAME}.tmp"
    tmp.write_bytes(gzip.compress(content.encode("utf-8")))
    os.replace(tmp, scope_dir / _UNIFIED_NAME)


def prune_expired(cache_root: Path, ttl_days: int = 7) -> None:
    """Remove manifest entries past TTL; delete scope dir when all entries expire."""
    if not cache_root.exists():
        return
    cutoff = time.time() - ttl_days * 86400

    for scope_dir in cache_root.iterdir():
        if not scope_dir.is_dir():
            continue
        manifest_path = scope_dir / _MANIFEST_NAME
        if not manifest_path.exists():
            continue
        manifest = load_manifest(scope_dir)
        live = {k: v for k, v in manifest.items() if v["expires_at"] > cutoff}
        if len(live) == len(manifest):
            continue
        if live:
            save_manifest(scope_dir, live)
        else:
            _remove_scope_dir(scope_dir)


def _remove_scope_dir(scope_dir: Path) -> None:
    for child in scope_dir.iterdir():
        child.unlink(missing_ok=True)
    scope_dir.rmdir()


def ensure_gitignore(
    repo_root: Path,
    *,
    prompt_fn: Callable[[str], str] | None = None,
) -> None:
    """Append .docspatch to .gitignore idempotently.

    When .gitignore is absent, calls prompt_fn (or input) to ask the user
    before creating it. No-op if the entry is already present.
    """
    gitignore = repo_root / ".gitignore"

    if not gitignore.exists():
        ask = prompt_fn if prompt_fn is not None else input
        answer = ask("No .gitignore found. Create one and add .docspatch? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            return
        gitignore.write_text(f"{_GITIGNORE_ENTRY}\n", encoding="utf-8")
        return

    content = gitignore.read_text(encoding="utf-8")
    existing_lines = {line.strip() for line in content.splitlines()}
    if _GITIGNORE_ENTRY in existing_lines or _GITIGNORE_ENTRY.rstrip("/") in existing_lines:
        return

    sep = "\n" if content.endswith("\n") else "\n\n"
    gitignore.write_text(content + sep + _GITIGNORE_ENTRY + "\n", encoding="utf-8")
