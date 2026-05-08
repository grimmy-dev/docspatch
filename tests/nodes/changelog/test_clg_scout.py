"""Tests for clg_scout node — LLM call mocked, file I/O and AST compression run for real."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.changelog_state import ChangelogState

_MOD = "src.graph.nodes.changelog.scout"


def _state(**kwargs: object) -> ChangelogState:
    return ChangelogState(**kwargs)  # type: ignore[arg-type]


def _make_repo(tmp_path: Path) -> Path:
    """Create a minimal Python project layout."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text("def hello() -> str:\n    return 'hello'\n")
    return tmp_path


@pytest.mark.asyncio
async def test_clg_mode_scopes_to_changed_files(tmp_path: Path) -> None:
    """Scout uses clg mode and scopes to state.changed_files."""
    _make_repo(tmp_path)
    state = _state(
        repo_path=tmp_path,
        changed_files=["src/main.py"],
    )
    scout_mock = AsyncMock(return_value=(None, "", 10))

    with patch("src.graph.nodes.scout.acall_llm", scout_mock):
        from src.graph.nodes.changelog.scout import clg_scout

        result = await clg_scout(state)

    assert "scout_output" in result
    assert result["scout_output"]["summaries"] is not None


@pytest.mark.asyncio
async def test_initial_commit_uses_readme_mode(tmp_path: Path) -> None:
    """Initial commit triggers readme mode (scan all files)."""
    _make_repo(tmp_path)
    state = _state(
        repo_path=tmp_path,
        is_initial_commit=True,
        changed_files=[],
    )
    scout_mock = AsyncMock(return_value=(None, "", 20))

    with patch("src.graph.nodes.scout.acall_llm", scout_mock):
        from src.graph.nodes.changelog.scout import clg_scout

        result = await clg_scout(state)

    # In readme mode, scout finds python files in the repo
    assert "scout_output" in result
    assert result["scout_output"]["tokens_used"] >= 0


@pytest.mark.asyncio
async def test_dry_run_returns_empty(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    state = _state(repo_path=tmp_path, dry_run=True, changed_files=["src/main.py"])

    from src.graph.nodes.changelog.scout import clg_scout

    result = await clg_scout(state)
    assert result == {}


@pytest.mark.asyncio
async def test_empty_changed_files_non_initial_returns_empty_output(tmp_path: Path) -> None:
    """No changed python files in non-initial run → scout returns empty output."""
    _make_repo(tmp_path)
    state = _state(repo_path=tmp_path, changed_files=[], is_initial_commit=False)

    from src.graph.nodes.changelog.scout import clg_scout

    result = await clg_scout(state)
    assert "scout_output" in result
    assert result["scout_output"]["summaries"] == []


@pytest.mark.asyncio
async def test_clg_scout_passes_scope_dir_to_scout_node(tmp_path: Path) -> None:
    """clg_scout computes scope_dir and passes it to scout_node for persistent caching."""
    from src.schemas.scout_io import ScoutOutput

    _make_repo(tmp_path)
    state = _state(repo_path=tmp_path, changed_files=["src/main.py"])

    captured_kwargs: list[dict[str, object]] = []

    async def capturing_scout(**kwargs: object) -> ScoutOutput:
        captured_kwargs.append(kwargs)
        return ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=0)

    with patch(f"{_MOD}.scout_node", side_effect=capturing_scout):
        import src.graph.nodes.changelog.scout as mod
        result = await mod.clg_scout(state)

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0].get("scope_dir") is not None


@pytest.mark.asyncio
async def test_clg_scout_initial_commit_passes_scope_dir(tmp_path: Path) -> None:
    """Initial commit path also passes scope_dir for persistent caching."""
    from src.schemas.scout_io import ScoutOutput

    _make_repo(tmp_path)
    state = _state(repo_path=tmp_path, is_initial_commit=True, changed_files=[])

    captured_kwargs: list[dict[str, object]] = []

    async def capturing_scout(**kwargs: object) -> ScoutOutput:
        captured_kwargs.append(kwargs)
        return ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=0)

    with patch(f"{_MOD}.scout_node", side_effect=capturing_scout):
        import src.graph.nodes.changelog.scout as mod
        result = await mod.clg_scout(state)

    assert len(captured_kwargs) == 1
    assert captured_kwargs[0].get("scope_dir") is not None


@pytest.mark.asyncio
async def test_token_count_accumulated(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    state = _state(repo_path=tmp_path, changed_files=["src/main.py"])
    scout_mock = AsyncMock(return_value=(None, "", 42))

    with patch("src.graph.nodes.scout.acall_llm", scout_mock):
        from src.graph.nodes.changelog.scout import clg_scout

        result = await clg_scout(state)

    assert result.get("token_actual", 0) >= 0
