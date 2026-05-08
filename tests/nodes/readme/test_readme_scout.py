"""Tests for readme_scout and readme_aggregator LangGraph nodes."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.readme_state import ReadmeState


def _state(**kwargs: object) -> ReadmeState:
    return ReadmeState(repo_path=Path("/repo"), target_path=Path("/repo"), **kwargs)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# readme_scout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_scout_dry_run_returns_empty() -> None:
    from src.graph.nodes.readme.scout import readme_scout

    state = _state(dry_run=True)
    result = await readme_scout(state)
    assert result == {}


@pytest.mark.asyncio
async def test_readme_scout_cancelled_returns_empty() -> None:
    from src.graph.nodes.readme.scout import readme_scout

    state = _state()
    with patch("src.graph.nodes.readme.scout.is_cancelled", return_value=True):
        result = await readme_scout(state)
    assert result == {}


@pytest.mark.asyncio
async def test_readme_scout_full_scan_when_no_changed_files(tmp_path: Path) -> None:
    """No changed files → scout processes all files in target_path."""
    from src.graph.nodes.readme.scout import readme_scout
    from src.schemas.scout_io import ScoutOutput

    state = ReadmeState(repo_path=tmp_path, target_path=tmp_path)
    scout_output = ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=42)

    with patch("src.graph.nodes.readme.scout.scout_node", new=AsyncMock(return_value=scout_output)) as mock_scout:
        result = await readme_scout(state)

    call_kwargs = mock_scout.call_args.kwargs
    assert call_kwargs["changed_files"] is None  # full scan
    assert call_kwargs["mode"] == "readme"
    assert result.get("scout_output") == scout_output
    assert result.get("token_actual") == 42


@pytest.mark.asyncio
async def test_readme_scout_incremental_passes_changed_files(tmp_path: Path) -> None:
    """Non-empty diff_changed_files → scout scopes to those files."""
    from src.graph.nodes.readme.scout import readme_scout
    from src.schemas.scout_io import ScoutOutput

    changed = ["src/foo.py", "src/bar.py"]
    state = ReadmeState(repo_path=tmp_path, target_path=tmp_path, diff_changed_files=changed)
    scout_output = ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=10)

    with patch("src.graph.nodes.readme.scout.scout_node", new=AsyncMock(return_value=scout_output)) as mock_scout:
        result = await readme_scout(state)

    call_kwargs = mock_scout.call_args.kwargs
    assert call_kwargs["changed_files"] == changed
    assert result.get("scout_output") == scout_output


@pytest.mark.asyncio
async def test_readme_scout_passes_existing_readme(tmp_path: Path) -> None:
    """Existing README is passed as existing_doc anchor."""
    from src.graph.nodes.readme.scout import readme_scout
    from src.schemas.scout_io import ScoutOutput

    state = ReadmeState(repo_path=tmp_path, target_path=tmp_path, existing_readme="# Old README")
    scout_output = ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=5)

    with patch("src.graph.nodes.readme.scout.scout_node", new=AsyncMock(return_value=scout_output)) as mock_scout:
        await readme_scout(state)

    call_kwargs = mock_scout.call_args.kwargs
    assert call_kwargs["existing_doc"] == "# Old README"


# ---------------------------------------------------------------------------
# readme_aggregator
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_aggregator_dry_run_returns_empty() -> None:
    from src.graph.nodes.readme.aggregator import readme_aggregator
    from src.schemas.scout_io import ScoutOutput

    state = _state(dry_run=True, scout_output=ScoutOutput(summaries=[], grouped={"src": []}, cache_hits=0, tokens_used=0))
    result = await readme_aggregator(state)
    assert result == {}


@pytest.mark.asyncio
async def test_readme_aggregator_no_scout_output_returns_empty() -> None:
    from src.graph.nodes.readme.aggregator import readme_aggregator

    state = _state()
    result = await readme_aggregator(state)
    assert result == {}


@pytest.mark.asyncio
async def test_readme_aggregator_calls_aggregator_node(tmp_path: Path) -> None:
    """Aggregator node is called with grouped summaries; result stored in aggregated_context."""
    from src.graph.nodes.readme.aggregator import readme_aggregator
    from src.schemas.scout_io import FileSummary, ScoutOutput

    grouped = {"src": [FileSummary(path="src/foo.py", summary="Foo module", key_symbols=["foo"])]}
    scout_out = ScoutOutput(summaries=[], grouped=grouped, cache_hits=0, tokens_used=0)
    state = ReadmeState(repo_path=tmp_path, target_path=tmp_path, scout_output=scout_out)

    with patch("src.graph.nodes.readme.aggregator.aggregator_node", new=AsyncMock(return_value="Unified context.")) as mock_agg:
        result = await readme_aggregator(state)

    mock_agg.assert_called_once()
    call_kwargs = mock_agg.call_args.kwargs
    assert call_kwargs["grouped"] == grouped
    assert result.get("aggregated_context") == "Unified context."
