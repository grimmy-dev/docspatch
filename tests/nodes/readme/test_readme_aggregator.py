"""Tests for readme_aggregator persistent cache behavior (Issue 12)."""

import gzip
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.readme_state import ReadmeState
from src.schemas.scout_io import FileSummary, ScoutOutput

_LLM_MOD = "src.graph.nodes.aggregator"
_CACHE_SUBDIR = Path(".docspatch") / "cache"


def _summary(path: str) -> FileSummary:
    return FileSummary(path=path, summary="Does stuff.", key_symbols=["sym"])


def _scout_output(cache_hits: int, total: int) -> ScoutOutput:
    sums = [_summary(f"src/mod{i}.py") for i in range(total)]
    grouped = {"src": sums}
    return ScoutOutput(summaries=sums, grouped=grouped, cache_hits=cache_hits, tokens_used=0)


def _state(tmp_path: Path, **kwargs: object) -> ReadmeState:
    return ReadmeState(repo_root=tmp_path, **kwargs)  # type: ignore[arg-type]


def _write_unified(scope_dir: Path, content: str) -> None:
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / "unified.gz").write_bytes(gzip.compress(content.encode()))


def _get_scope_dir(tmp_path: Path) -> Path:
    from src.utils.persistent_cache import get_scope_dir
    cache_root = tmp_path / _CACHE_SUBDIR
    return get_scope_dir(cache_root, tmp_path, tmp_path)


# ---------------------------------------------------------------------------
# Tracer — all cache hits: LLM skipped, return unified.gz content
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_aggregator_skips_llm_when_all_cache_hits(tmp_path: Path) -> None:
    scope_dir = _get_scope_dir(tmp_path)
    _write_unified(scope_dir, "Cached unified context.")

    state = _state(tmp_path, scout_output=_scout_output(cache_hits=2, total=2))
    llm_mock = AsyncMock(return_value=(None, "should not be called", 0))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.readme.aggregator import readme_aggregator
        result = await readme_aggregator(state)

    assert result["aggregated_context"] == "Cached unified context."
    llm_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# Files changed — LLM called, unified.gz written after success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_aggregator_calls_llm_and_writes_unified_when_files_changed(tmp_path: Path) -> None:
    scope_dir = _get_scope_dir(tmp_path)
    _write_unified(scope_dir, "Old unified context.")

    state = _state(tmp_path, scout_output=_scout_output(cache_hits=1, total=2))
    llm_mock = AsyncMock(return_value=(None, "New unified context.", 20))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.readme.aggregator import readme_aggregator
        result = await readme_aggregator(state)

    assert result["aggregated_context"] == "New unified context."
    llm_mock.assert_awaited_once()

    written = gzip.decompress((scope_dir / "unified.gz").read_bytes()).decode()
    assert written == "New unified context."


# ---------------------------------------------------------------------------
# First run — no unified.gz present: LLM called, unified.gz created
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_aggregator_first_run_creates_unified_gz(tmp_path: Path) -> None:
    scope_dir = _get_scope_dir(tmp_path)
    assert not (scope_dir / "unified.gz").exists()

    state = _state(tmp_path, scout_output=_scout_output(cache_hits=0, total=1))
    llm_mock = AsyncMock(return_value=(None, "First run context.", 15))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.readme.aggregator import readme_aggregator
        result = await readme_aggregator(state)

    assert result["aggregated_context"] == "First run context."
    written = gzip.decompress((scope_dir / "unified.gz").read_bytes()).decode()
    assert written == "First run context."


# ---------------------------------------------------------------------------
# ensure_gitignore wired on first cache write
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_aggregator_calls_ensure_gitignore_on_write(tmp_path: Path) -> None:
    state = _state(tmp_path, scout_output=_scout_output(cache_hits=0, total=1))
    llm_mock = AsyncMock(return_value=(None, "Context.", 10))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock), \
         patch("src.graph.nodes.readme.aggregator.ensure_gitignore") as gi_mock:
        from src.graph.nodes.readme.aggregator import readme_aggregator
        await readme_aggregator(state)

    gi_mock.assert_called_once()


# ---------------------------------------------------------------------------
# No repo_root — no caching, behaves as before
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_aggregator_without_repo_root_does_not_cache(tmp_path: Path) -> None:
    state = ReadmeState(scout_output=_scout_output(cache_hits=0, total=1))
    llm_mock = AsyncMock(return_value=(None, "Result.", 10))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.readme.aggregator import readme_aggregator
        result = await readme_aggregator(state)

    assert result["aggregated_context"] == "Result."
    llm_mock.assert_awaited_once()
