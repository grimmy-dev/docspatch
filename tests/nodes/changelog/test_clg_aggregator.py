"""Tests for clg_aggregator node — LLM call mocked."""

import gzip
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.changelog_state import ChangelogState
from src.schemas.scout_io import FileSummary, ScoutOutput

_LLM_MOD = "src.graph.nodes.aggregator"
_CACHE_SUBDIR = Path(".docspatch") / "cache"


def _state(**kwargs: object) -> ChangelogState:
    return ChangelogState(**kwargs)  # type: ignore[arg-type]


def _scout_output(cache_hits: int = 0, total: int = 1) -> ScoutOutput:
    sums = [FileSummary(path=f"src/mod{i}.py", summary="Does stuff.", key_symbols=[]) for i in range(total)]
    grouped = {"src": sums}
    return ScoutOutput(summaries=sums, grouped=grouped, cache_hits=cache_hits, tokens_used=10)


def _get_scope_dir(tmp_path: Path) -> Path:
    from src.utils.persistent_cache import get_scope_dir
    return get_scope_dir(tmp_path / _CACHE_SUBDIR, tmp_path, tmp_path)


def _write_unified(scope_dir: Path, content: str) -> None:
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / "unified.gz").write_bytes(gzip.compress(content.encode()))


@pytest.mark.asyncio
async def test_aggregator_calls_llm_and_returns_context() -> None:
    state = _state(scout_output=_scout_output())
    llm_mock = AsyncMock(return_value=(None, "Unified context text.", 30))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.changelog.aggregator import clg_aggregator

        result = await clg_aggregator(state)

    assert result["aggregated_context"] == "Unified context text."
    llm_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_aggregator_returns_empty_when_no_scout_output() -> None:
    state = _state(scout_output=None)

    from src.graph.nodes.changelog.aggregator import clg_aggregator

    result = await clg_aggregator(state)
    assert result == {}


@pytest.mark.asyncio
async def test_aggregator_returns_empty_when_grouped_empty() -> None:
    empty_output = ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=0)
    state = _state(scout_output=empty_output)

    from src.graph.nodes.changelog.aggregator import clg_aggregator

    result = await clg_aggregator(state)
    assert result == {}


@pytest.mark.asyncio
async def test_aggregator_returns_empty_on_dry_run() -> None:
    state = _state(scout_output=_scout_output(), dry_run=True)

    from src.graph.nodes.changelog.aggregator import clg_aggregator

    result = await clg_aggregator(state)
    assert result == {}


@pytest.mark.asyncio
async def test_aggregator_single_llm_call(tmp_path: Path) -> None:
    """Aggregator makes exactly one LLM call regardless of how many directories."""
    summaries = [
        FileSummary(path="src/a.py", summary="Module A.", key_symbols=["A"]),
        FileSummary(path="lib/b.py", summary="Module B.", key_symbols=["B"]),
    ]
    grouped = {
        "src": [summaries[0]],
        "lib": [summaries[1]],
    }
    output = ScoutOutput(summaries=summaries, grouped=grouped, cache_hits=0, tokens_used=20)
    state = _state(scout_output=output)
    llm_mock = AsyncMock(return_value=(None, "Combined.", 15))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.changelog.aggregator import clg_aggregator

        await clg_aggregator(state)

    assert llm_mock.await_count == 1


# ---------------------------------------------------------------------------
# Persistent cache behavior (Issue 12)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clg_aggregator_skips_llm_when_all_cache_hits(tmp_path: Path) -> None:
    scope_dir = _get_scope_dir(tmp_path)
    _write_unified(scope_dir, "Cached CLG context.")

    state = _state(repo_path=tmp_path, scout_output=_scout_output(cache_hits=2, total=2))
    llm_mock = AsyncMock(return_value=(None, "should not be called", 0))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.changelog.aggregator import clg_aggregator
        result = await clg_aggregator(state)

    assert result["aggregated_context"] == "Cached CLG context."
    llm_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_clg_aggregator_calls_llm_and_writes_unified_when_files_changed(tmp_path: Path) -> None:
    scope_dir = _get_scope_dir(tmp_path)
    _write_unified(scope_dir, "Old CLG context.")

    state = _state(repo_path=tmp_path, scout_output=_scout_output(cache_hits=1, total=2))
    llm_mock = AsyncMock(return_value=(None, "New CLG context.", 20))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.changelog.aggregator import clg_aggregator
        result = await clg_aggregator(state)

    assert result["aggregated_context"] == "New CLG context."
    llm_mock.assert_awaited_once()
    written = gzip.decompress((scope_dir / "unified.gz").read_bytes()).decode()
    assert written == "New CLG context."


@pytest.mark.asyncio
async def test_clg_aggregator_first_run_creates_unified_gz(tmp_path: Path) -> None:
    scope_dir = _get_scope_dir(tmp_path)
    assert not (scope_dir / "unified.gz").exists()

    state = _state(repo_path=tmp_path, scout_output=_scout_output(cache_hits=0, total=1))
    llm_mock = AsyncMock(return_value=(None, "First run CLG.", 15))

    with patch(f"{_LLM_MOD}.acall_llm", llm_mock):
        from src.graph.nodes.changelog.aggregator import clg_aggregator
        result = await clg_aggregator(state)

    assert result["aggregated_context"] == "First run CLG."
    written = gzip.decompress((scope_dir / "unified.gz").read_bytes()).decode()
    assert written == "First run CLG."
