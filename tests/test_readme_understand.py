"""Tests for readme_understand node — module selection, content reading, hash caching."""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.readme_state import ReadmeState


def _state(**kwargs: object) -> ReadmeState:
    return ReadmeState(repo_path=Path("/repo"), target_path=Path("/repo"), **kwargs)  # type: ignore[arg-type]


def _sym_hash(symbols: list[str]) -> str:
    return hashlib.sha256("|".join(symbols).encode()).hexdigest()[:16]


def _make_llm_result(text: str, tokens: int = 10) -> tuple[None, str, int]:
    return (None, text, tokens)


# ---------------------------------------------------------------------------
# Pure helpers — module selection
# ---------------------------------------------------------------------------


def test_select_modules_caps_compact() -> None:
    from src.graph.nodes.readme.understand import _select_modules

    api = {f"mod_{i}.py": [f"fn_{i}"] for i in range(20)}
    result = _select_modules(api, "compact", [])
    assert len(result) == 5


def test_select_modules_caps_detailed() -> None:
    from src.graph.nodes.readme.understand import _select_modules

    api = {f"mod_{i}.py": [f"fn_{i}"] for i in range(20)}
    result = _select_modules(api, "detailed", [])
    assert len(result) == 10


def test_select_modules_prioritises_changed_files() -> None:
    from src.graph.nodes.readme.understand import _select_modules

    api = {"utils/helper.py": ["fn"], "changed.py": ["fn2"], "other.py": ["fn3"]}
    result = _select_modules(api, "compact", ["changed.py"])
    assert result[0] == "changed.py"


def test_select_modules_prioritises_main() -> None:
    from src.graph.nodes.readme.understand import _select_modules

    api = {"src/__main__.py": ["main"], "src/utils/helper.py": ["util"]}
    result = _select_modules(api, "compact", [])
    assert result[0] == "src/__main__.py"


# ---------------------------------------------------------------------------
# Pure helpers — hash and formatting
# ---------------------------------------------------------------------------


def test_hash_module_is_deterministic() -> None:
    from src.graph.nodes.readme.understand import _hash_module

    symbols = ["foo", "bar", "baz"]
    assert _hash_module(symbols) == _hash_module(symbols)
    assert len(_hash_module(symbols)) == 16


def test_hash_module_differs_on_symbol_change() -> None:
    from src.graph.nodes.readme.understand import _hash_module

    assert _hash_module(["foo"]) != _hash_module(["bar"])


def test_build_understanding_string_contains_all_modules() -> None:
    from src.graph.nodes.readme.understand import _build_understanding_string

    summaries = {"mod_a": "Does A things.", "mod_b": "Does B things."}
    result = _build_understanding_string(summaries)
    assert "mod_a" in result
    assert "mod_b" in result
    assert result.startswith("Project Understanding:")


def test_partition_modules_splits_correctly() -> None:
    from src.graph.nodes.readme.understand import _hash_module, _partition_modules

    symbols_a = ["foo", "bar"]
    symbols_b = ["baz"]
    cached_hashes = {"mod_a": _hash_module(symbols_a)}

    public_api = {"mod_a": symbols_a, "mod_b": symbols_b}
    fresh, cached = _partition_modules(list(public_api), public_api, cached_hashes)

    assert "mod_b" in fresh
    assert "mod_a" in cached
    assert "mod_b" not in cached
    assert "mod_a" not in fresh


# ---------------------------------------------------------------------------
# Async node tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_returns_empty() -> None:
    from src.graph.nodes.readme.understand import readme_understand

    state = _state(dry_run=True, public_api={"mod.py": ["foo"]})
    result = await readme_understand(state)
    assert result == {}


@pytest.mark.asyncio
async def test_cancelled_returns_empty() -> None:
    from src.graph.nodes.readme.understand import readme_understand

    state = _state(public_api={"mod.py": ["foo"]})
    with patch("src.graph.nodes.readme.understand.is_cancelled", return_value=True):
        result = await readme_understand(state)
    assert result == {}


@pytest.mark.asyncio
async def test_empty_public_api_returns_empty() -> None:
    from src.graph.nodes.readme.understand import readme_understand

    state = _state(public_api={})
    result = await readme_understand(state)
    assert result == {}


@pytest.mark.asyncio
async def test_fresh_module_triggers_llm_call() -> None:
    from src.graph.nodes.readme.understand import readme_understand

    public_api = {"src/foo.py": ["func_a", "func_b"]}
    state = _state(public_api=public_api)

    mock_llm = AsyncMock(return_value=_make_llm_result("Handles foo operations.", tokens=15))
    with (
        patch("src.graph.nodes.readme.understand._read_module_content", new=AsyncMock(return_value="def func_a(): pass")),
        patch("src.graph.nodes.readme.understand.acall_llm", mock_llm),
    ):
        result = await readme_understand(state)

    mock_llm.assert_called_once()
    assert result.get("module_summaries", {}).get("src/foo.py") == "Handles foo operations."
    assert result.get("token_actual") == 15


@pytest.mark.asyncio
async def test_cached_module_skips_llm_call() -> None:
    from src.graph.nodes.readme.understand import readme_understand

    symbols = ["func_a"]
    existing_hash = _sym_hash(symbols)
    public_api = {"src/bar.py": symbols}
    state = _state(
        public_api=public_api,
        module_summaries={"src/bar.py": "Existing cached summary."},
        module_hashes={"src/bar.py": existing_hash},
    )

    mock_llm = AsyncMock()
    with (
        patch("src.graph.nodes.readme.understand._read_module_content", new=AsyncMock(return_value="def func_a(): pass")),
        patch("src.graph.nodes.readme.understand.acall_llm", mock_llm),
    ):
        result = await readme_understand(state)

    mock_llm.assert_not_called()
    assert result.get("module_summaries", {}).get("src/bar.py") == "Existing cached summary."
    assert result.get("token_actual", 0) == 0


@pytest.mark.asyncio
async def test_project_understanding_contains_all_module_names() -> None:
    from src.graph.nodes.readme.understand import readme_understand

    public_api = {"mod_a.py": ["alpha"], "mod_b.py": ["beta"]}
    state = _state(public_api=public_api)

    async def fake_llm(_model: str, _system: str, prompt: str, **__: object) -> tuple[None, str, int]:
        mod = "mod_a" if "mod_a" in prompt else "mod_b"
        return (None, f"Summary for {mod}.", 5)

    with (
        patch("src.graph.nodes.readme.understand._read_module_content", new=AsyncMock(return_value="")),
        patch("src.graph.nodes.readme.understand.acall_llm", side_effect=fake_llm),
    ):
        result = await readme_understand(state)

    understanding: str = result.get("project_understanding") or ""
    assert "mod_a" in understanding
    assert "mod_b" in understanding


@pytest.mark.asyncio
async def test_mixed_fresh_and_cached_merges_correctly() -> None:
    from src.graph.nodes.readme.understand import readme_understand

    cached_symbols = ["existing_fn"]
    fresh_symbols = ["new_fn"]
    existing_hash = _sym_hash(cached_symbols)

    public_api = {"cached_mod.py": cached_symbols, "fresh_mod.py": fresh_symbols}
    state = _state(
        public_api=public_api,
        module_summaries={"cached_mod.py": "Cached summary."},
        module_hashes={"cached_mod.py": existing_hash},
    )

    mock_llm = AsyncMock(return_value=_make_llm_result("Fresh summary.", tokens=8))
    with (
        patch("src.graph.nodes.readme.understand._read_module_content", new=AsyncMock(return_value="")),
        patch("src.graph.nodes.readme.understand.acall_llm", mock_llm),
    ):
        result = await readme_understand(state)

    mock_llm.assert_called_once()
    summaries = result.get("module_summaries", {})
    assert summaries.get("cached_mod.py") == "Cached summary."
    assert summaries.get("fresh_mod.py") == "Fresh summary."
    assert result.get("token_actual") == 8
