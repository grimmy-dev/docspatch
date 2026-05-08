"""Tests for persistent_cache — manifest, gzip, key, TTL, gitignore utilities."""

import time
from pathlib import Path

from src.utils.persistent_cache import (
    compute_cache_key,
    ensure_gitignore,
    get_scope_hash,
    load_manifest,
    prune_expired,
    read_unified,
    save_manifest,
    write_unified,
)

# ── compute_cache_key ────────────────────────────────────────────────────────


def test_compute_cache_key_is_deterministic() -> None:
    k1 = compute_cache_key("abc", "gemini-flash", "v1")
    k2 = compute_cache_key("abc", "gemini-flash", "v1")
    assert k1 == k2


def test_compute_cache_key_differs_on_model_change() -> None:
    k1 = compute_cache_key("abc", "model-a", "v1")
    k2 = compute_cache_key("abc", "model-b", "v1")
    assert k1 != k2


def test_compute_cache_key_differs_on_hash_change() -> None:
    k1 = compute_cache_key("hash1", "model", "v1")
    k2 = compute_cache_key("hash2", "model", "v1")
    assert k1 != k2


def test_compute_cache_key_differs_on_prompt_version_change() -> None:
    k1 = compute_cache_key("abc", "model", "v1")
    k2 = compute_cache_key("abc", "model", "v2")
    assert k1 != k2


# ── get_scope_hash ───────────────────────────────────────────────────────────


def test_get_scope_hash_is_deterministic() -> None:
    h1 = get_scope_hash(Path("/repo/src"), Path("/repo"))
    h2 = get_scope_hash(Path("/repo/src"), Path("/repo"))
    assert h1 == h2


def test_get_scope_hash_differs_for_different_targets() -> None:
    h1 = get_scope_hash(Path("/repo/src"), Path("/repo"))
    h2 = get_scope_hash(Path("/repo/lib"), Path("/repo"))
    assert h1 != h2


# ── manifest round-trip ──────────────────────────────────────────────────────


def test_manifest_round_trip(tmp_path: Path) -> None:
    scope_dir = tmp_path / "scope"
    manifest = {
        "src/foo.py": {"key": "abc123", "expires_at": 9999999999.0},
        "src/bar.py": {"key": "def456", "expires_at": 9999999999.0},
    }
    save_manifest(scope_dir, manifest)
    loaded = load_manifest(scope_dir)
    assert loaded["src/foo.py"]["key"] == "abc123"
    assert loaded["src/bar.py"]["key"] == "def456"


def test_load_manifest_returns_empty_when_absent(tmp_path: Path) -> None:
    result = load_manifest(tmp_path / "no_such_scope")
    assert result == {}


def test_load_manifest_returns_empty_on_corrupt_json(tmp_path: Path) -> None:
    scope_dir = tmp_path / "scope"
    scope_dir.mkdir()
    (scope_dir / "manifest.json").write_text("not json", encoding="utf-8")
    result = load_manifest(scope_dir)
    assert result == {}


def test_save_manifest_creates_parent_dirs(tmp_path: Path) -> None:
    scope_dir = tmp_path / "deep" / "nested" / "scope"
    save_manifest(scope_dir, {})
    assert (scope_dir / "manifest.json").exists()


# ── gzip round-trip ──────────────────────────────────────────────────────────


def test_unified_round_trip(tmp_path: Path) -> None:
    scope_dir = tmp_path / "scope"
    content = "This is the unified context.\nWith multiple lines.\n"
    write_unified(scope_dir, content)
    result = read_unified(scope_dir)
    assert result == content


def test_read_unified_returns_none_when_absent(tmp_path: Path) -> None:
    result = read_unified(tmp_path / "no_such_scope")
    assert result is None


def test_write_unified_creates_parent_dirs(tmp_path: Path) -> None:
    scope_dir = tmp_path / "deep" / "scope"
    write_unified(scope_dir, "hello")
    assert (scope_dir / "unified.gz").exists()


def test_read_unified_returns_none_on_corrupt_file(tmp_path: Path) -> None:
    scope_dir = tmp_path / "scope"
    scope_dir.mkdir()
    (scope_dir / "unified.gz").write_bytes(b"not gzip data")
    result = read_unified(scope_dir)
    assert result is None


# ── prune_expired ────────────────────────────────────────────────────────────


def test_prune_expired_removes_expired_entries(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    scope_dir = cache_root / "abc123"
    now = time.time()
    manifest = {
        "src/old.py": {"key": "k1", "expires_at": now - 86400 * 8},  # 8 days ago — expired
        "src/new.py": {"key": "k2", "expires_at": now + 86400},  # future — live
    }
    save_manifest(scope_dir, manifest)

    prune_expired(cache_root, ttl_days=7)

    result = load_manifest(scope_dir)
    assert "src/old.py" not in result
    assert "src/new.py" in result


def test_prune_expired_deletes_scope_dir_when_all_expired(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    scope_dir = cache_root / "abc123"
    now = time.time()
    manifest = {
        "src/old.py": {"key": "k1", "expires_at": now - 86400 * 10},
    }
    save_manifest(scope_dir, manifest)

    prune_expired(cache_root, ttl_days=7)

    assert not scope_dir.exists()


def test_prune_expired_no_op_when_cache_absent(tmp_path: Path) -> None:
    prune_expired(tmp_path / "no_cache", ttl_days=7)  # must not raise


def test_prune_expired_leaves_live_scope_dir(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    scope_dir = cache_root / "abc123"
    manifest = {
        "src/new.py": {"key": "k1", "expires_at": time.time() + 86400 * 30},
    }
    save_manifest(scope_dir, manifest)

    prune_expired(cache_root, ttl_days=7)

    assert scope_dir.exists()
    assert load_manifest(scope_dir) != {}


# ── ensure_gitignore ─────────────────────────────────────────────────────────


def test_ensure_gitignore_appends_when_entry_absent(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("__pycache__/\n", encoding="utf-8")

    ensure_gitignore(tmp_path)

    content = gitignore.read_text(encoding="utf-8")
    assert ".docspatch" in content


def test_ensure_gitignore_idempotent_when_already_present(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("__pycache__/\n.docspatch\n", encoding="utf-8")

    ensure_gitignore(tmp_path)

    content = gitignore.read_text(encoding="utf-8")
    assert content.count(".docspatch") == 1


def test_ensure_gitignore_creates_file_when_user_confirms(tmp_path: Path) -> None:
    ensure_gitignore(tmp_path, prompt_fn=lambda _: "y")

    gitignore = tmp_path / ".gitignore"
    assert gitignore.exists()
    assert ".docspatch" in gitignore.read_text(encoding="utf-8")


def test_ensure_gitignore_skips_creation_when_user_declines(tmp_path: Path) -> None:
    ensure_gitignore(tmp_path, prompt_fn=lambda _: "n")

    assert not (tmp_path / ".gitignore").exists()


def test_ensure_gitignore_no_duplicate_on_repeated_call(tmp_path: Path) -> None:
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("", encoding="utf-8")

    ensure_gitignore(tmp_path)
    ensure_gitignore(tmp_path)

    content = gitignore.read_text(encoding="utf-8")
    assert content.count(".docspatch") == 1
