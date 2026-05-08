"""Tests for clg_aggregator node — LLM call mocked."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.changelog_state import ChangelogState
from src.schemas.scout_io import FileSummary, ScoutOutput

_LLM_MOD = "src.graph.nodes.aggregator"


def _state(**kwargs: object) -> ChangelogState:
    return ChangelogState(**kwargs)  # type: ignore[arg-type]


def _scout_output(summaries: list[FileSummary] | None = None) -> ScoutOutput:
    sums = summaries or [FileSummary(path="src/main.py", summary="Does main things.", key_symbols=["hello"])]
    grouped = {"src": sums}
    return ScoutOutput(summaries=sums, grouped=grouped, cache_hits=0, tokens_used=10)


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
