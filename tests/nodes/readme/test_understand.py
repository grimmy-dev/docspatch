"""Tests for readme_understand node — module selection, content reading, hash caching."""

import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.readme_io import UnderstandCache
from src.schemas.readme_state import ReadmeState


def _state(**kwargs: object) -> ReadmeState:
    return ReadmeState(repo_path=Path("/repo"), target_path=Path("/repo"), **kwargs)  # type: ignore[arg-type]


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _make_llm_result(text: str, tokens: int = 10) -> tuple[None, str, int]:
    return (None, text, tokens)


# ---------------------------------------------------------------------------
# Pure helpers — module selection
# ---------------------------------------------------------------------------


def test_select_modules_caps_compact() -> None:
    from src.graph.nodes.readme.understand import select_modules

    api = {f"mod_{i}.py": [f"fn_{i}"] for i in range(20)}
    result = select_modules(api, "compact", [])
    assert len(result) == 5


def test_select_modules_caps_detailed() -> None:
    from src.graph.nodes.readme.understand import select_modules

    api = {f"mod_{i}.py": [f"fn_{i}"] for i in range(20)}
    result = select_modules(api, "detailed", [])
    assert len(result) == 10


def test_select_modules_prioritises_changed_files() -> None:
    from src.graph.nodes.readme.understand import select_modules

    api = {"utils/helper.py": ["fn"], "changed.py": ["fn2"], "other.py": ["fn3"]}
    result = select_modules(api, "compact", ["changed.py"])
    assert result[0] == "changed.py"


def test_select_modules_prioritises_main() -> None:
    from src.graph.nodes.readme.understand import select_modules

    api = {"src/__main__.py": ["main"], "src/utils/helper.py": ["util"]}
    result = select_modules(api, "compact", [])
    assert result[0] == "src/__main__.py"


# ---------------------------------------------------------------------------
# Pure helpers — hash and formatting
# ---------------------------------------------------------------------------


def test_hash_content_is_deterministic() -> None:
    from src.utils.fs import hash_content

    content = "def foo(): pass\ndef bar(): pass"
    assert hash_content(content) == hash_content(content)
    assert len(hash_content(content)) == 16


def test_hash_content_differs_on_change() -> None:
    from src.utils.fs import hash_content

    assert hash_content("def foo(): pass") != hash_content("def bar(): pass")


def test_build_understanding_string_contains_all_modules() -> None:
    from src.graph.nodes.readme.understand import build_understanding_string

    summaries = {"mod_a": "Does A things.", "mod_b": "Does B things."}
    result = build_understanding_string(summaries)
    assert "mod_a" in result
    assert "mod_b" in result
    assert result.startswith("Project Understanding:")


def test_partition_modules_splits_correctly() -> None:
    from src.graph.nodes.readme.understand import partition_modules
    from src.utils.fs import hash_content

    content_a = "def foo(): pass\ndef bar(): pass"
    content_b = "def baz(): pass"
    contents = {"mod_a.py": content_a, "mod_b.py": content_b}
    cached_hashes = {"mod_a.py": hash_content(content_a)}

    fresh, cached = partition_modules(list(contents), cached_hashes, contents)

    assert "mod_b.py" in fresh
    assert "mod_a.py" in cached
    assert "mod_b.py" not in cached
    assert "mod_a.py" not in fresh


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
    cache: UnderstandCache = result.get("understand_cache") or UnderstandCache()
    assert cache.summaries.get("src/foo.py") == "Handles foo operations."
    assert result.get("token_actual") == 15


@pytest.mark.asyncio
async def test_cached_module_skips_llm_call() -> None:
    from src.graph.nodes.readme.understand import readme_understand

    fake_content = "def func_a(): pass"
    existing_hash = _content_hash(fake_content)
    public_api = {"src/bar.py": ["func_a"]}
    state = _state(
        public_api=public_api,
        understand_cache=UnderstandCache(
            summaries={"src/bar.py": "Existing cached summary."},
            hashes={"src/bar.py": existing_hash},
        ),
    )

    mock_llm = AsyncMock()
    with (
        patch("src.graph.nodes.readme.understand._read_module_content", new=AsyncMock(return_value=fake_content)),
        patch("src.graph.nodes.readme.understand.acall_llm", mock_llm),
    ):
        result = await readme_understand(state)

    mock_llm.assert_not_called()
    cache: UnderstandCache = result.get("understand_cache") or UnderstandCache()
    assert cache.summaries.get("src/bar.py") == "Existing cached summary."
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

    cached_content = "def existing_fn(): pass"
    existing_hash = _content_hash(cached_content)

    public_api = {"cached_mod.py": ["existing_fn"], "fresh_mod.py": ["new_fn"]}
    state = _state(
        public_api=public_api,
        understand_cache=UnderstandCache(
            summaries={"cached_mod.py": "Cached summary."},
            hashes={"cached_mod.py": existing_hash},
        ),
    )

    async def fake_read(path: object) -> str:
        return cached_content if "cached" in str(path) else ""

    mock_llm = AsyncMock(return_value=_make_llm_result("Fresh summary.", tokens=8))
    with (
        patch("src.graph.nodes.readme.understand._read_module_content", side_effect=fake_read),
        patch("src.graph.nodes.readme.understand.acall_llm", mock_llm),
    ):
        result = await readme_understand(state)

    mock_llm.assert_called_once()
    cache: UnderstandCache = result.get("understand_cache") or UnderstandCache()
    assert cache.summaries.get("cached_mod.py") == "Cached summary."
    assert cache.summaries.get("fresh_mod.py") == "Fresh summary."
    assert result.get("token_actual") == 8
