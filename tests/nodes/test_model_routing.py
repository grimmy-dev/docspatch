"""Tests for two-tier model routing — scout_model and writer_model config keys."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.config import AppConfig, AppDefaults, AppKeys


def _cfg(scout_model: str = "test-scout", writer_model: str = "test-writer") -> AppConfig:
    return AppConfig(defaults=AppDefaults(scout_model=scout_model, writer_model=writer_model), keys=AppKeys())


# ---------------------------------------------------------------------------
# Schema defaults
# ---------------------------------------------------------------------------


def test_scout_model_defaults_to_cheapest_google_model() -> None:
    assert AppDefaults().scout_model == "gemini-2.5-flash-lite"


def test_writer_model_defaults_to_google_pro() -> None:
    assert AppDefaults().writer_model == "gemini-2.5-pro"


def test_models_are_independently_overridable() -> None:
    cfg = AppConfig(defaults=AppDefaults(scout_model="cheap-scout", writer_model="big-writer"))
    assert cfg.defaults.scout_model == "cheap-scout"
    assert cfg.defaults.writer_model == "big-writer"


# ---------------------------------------------------------------------------
# ProviderConfig has scout_models
# ---------------------------------------------------------------------------


def test_each_provider_has_scout_models() -> None:
    from src.utils.llm.catalogue import PROVIDERS

    for name, provider in PROVIDERS.items():
        assert provider.scout_models, f"{name} has empty scout_models"


# ---------------------------------------------------------------------------
# readme_scout uses scout_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_scout_uses_scout_model(tmp_path: Path) -> None:
    from src.graph.nodes.readme.scout import readme_scout
    from src.schemas.readme_state import ReadmeState
    from src.schemas.scout_io import ScoutOutput

    state = ReadmeState(repo_path=tmp_path, target_path=tmp_path)
    out = ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=0)

    with (
        patch("src.graph.nodes.readme.scout.load", return_value=_cfg(scout_model="fast-cheap")),
        patch("src.graph.nodes.readme.scout.scout_node", new=AsyncMock(return_value=out)) as mock_scout,
    ):
        await readme_scout(state)

    assert mock_scout.call_args.kwargs["model_key"] == "fast-cheap"


# ---------------------------------------------------------------------------
# readme_aggregator uses scout_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_aggregator_uses_scout_model(tmp_path: Path) -> None:
    from src.graph.nodes.readme.aggregator import readme_aggregator
    from src.schemas.readme_state import ReadmeState
    from src.schemas.scout_io import FileSummary, ScoutOutput

    grouped = {"src": [FileSummary(path="src/foo.py", summary="Foo", key_symbols=[])]}
    scout_out = ScoutOutput(summaries=[], grouped=grouped, cache_hits=0, tokens_used=0)
    state = ReadmeState(repo_path=tmp_path, target_path=tmp_path, scout_output=scout_out)

    with (
        patch("src.graph.nodes.readme.aggregator.load", return_value=_cfg(scout_model="fast-cheap")),
        patch("src.graph.nodes.readme.aggregator.aggregator_node", new=AsyncMock(return_value="ctx")) as mock_agg,
    ):
        await readme_aggregator(state)

    assert mock_agg.call_args.kwargs["model_key"] == "fast-cheap"


# ---------------------------------------------------------------------------
# readme_llm uses writer_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_readme_llm_uses_writer_model(tmp_path: Path) -> None:
    from src.graph.nodes.readme.generate import readme_llm
    from src.schemas.readme_state import ReadmeState

    state = ReadmeState(repo_path=tmp_path, target_path=tmp_path, aggregated_context="ctx")
    llm_mock = AsyncMock(return_value=(None, "Generated README", 50))

    with (
        patch("src.graph.nodes.readme.generate.load", return_value=_cfg(writer_model="big-writer")),
        patch("src.graph.nodes.readme.generate.acall_llm", llm_mock),
    ):
        await readme_llm(state)

    assert llm_mock.call_args.args[0] == "big-writer"


# ---------------------------------------------------------------------------
# clg_scout uses scout_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clg_scout_uses_scout_model(tmp_path: Path) -> None:
    from src.graph.nodes.changelog.scout import clg_scout
    from src.schemas.changelog_state import ChangelogState
    from src.schemas.scout_io import ScoutOutput

    state = ChangelogState(repo_path=tmp_path, changed_files=["src/foo.py"])
    out = ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=0)

    with (
        patch("src.graph.nodes.changelog.scout.load", return_value=_cfg(scout_model="fast-cheap")),
        patch("src.graph.nodes.changelog.scout.scout_node", new=AsyncMock(return_value=out)) as mock_scout,
    ):
        await clg_scout(state)

    assert mock_scout.call_args.kwargs["model_key"] == "fast-cheap"


# ---------------------------------------------------------------------------
# clg_aggregator uses scout_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clg_aggregator_uses_scout_model() -> None:
    from src.graph.nodes.changelog.aggregator import clg_aggregator
    from src.schemas.changelog_state import ChangelogState
    from src.schemas.scout_io import FileSummary, ScoutOutput

    grouped = {"src": [FileSummary(path="src/foo.py", summary="Foo", key_symbols=[])]}
    scout_out = ScoutOutput(summaries=[], grouped=grouped, cache_hits=0, tokens_used=0)
    state = ChangelogState(scout_output=scout_out)

    with (
        patch("src.graph.nodes.changelog.aggregator.load", return_value=_cfg(scout_model="fast-cheap")),
        patch("src.graph.nodes.changelog.aggregator.aggregator_node", new=AsyncMock(return_value="ctx")) as mock_agg,
    ):
        await clg_aggregator(state)

    assert mock_agg.call_args.kwargs["model_key"] == "fast-cheap"


# ---------------------------------------------------------------------------
# clg_llm uses writer_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clg_llm_uses_writer_model() -> None:
    from src.graph.nodes.changelog.generate import clg_llm
    from src.schemas.changelog_state import ChangelogState

    state = ChangelogState(aggregated_context="ctx", commits=["abc feat: add thing"])
    llm_mock = AsyncMock(return_value=(None, "Entry", 50))

    with (
        patch("src.graph.nodes.changelog.generate.load", return_value=_cfg(writer_model="big-writer")),
        patch("src.graph.nodes.changelog.generate.acall_llm", llm_mock),
    ):
        await clg_llm(state)

    assert llm_mock.call_args.args[0] == "big-writer"
