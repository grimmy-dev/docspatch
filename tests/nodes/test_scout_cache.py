"""Tests for scout node in-run hash cache (Issue 4)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.schemas.scout_io import FileSummary


def _group_analysis(path: str, summary: str = "desc", symbols: list[str] | None = None) -> MagicMock:
    entry = MagicMock()
    entry.path = path
    entry.summary = summary
    entry.key_symbols = symbols or []
    group = MagicMock()
    group.files = [entry]
    return group


# ---------------------------------------------------------------------------
# Tracer bullet — first run populates cache, LLM fires, cache_hits=0
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_run_fires_llm_and_has_zero_cache_hits(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "mod.py").write_text("def mod(): pass\n")
    run_cache: dict[str, FileSummary] = {}
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (_group_analysis("mod.py"), "", 10)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        result = await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
            run_cache=run_cache,
        )

    assert call_count == 1
    assert result["cache_hits"] == 0
    assert len(run_cache) == 1


# ---------------------------------------------------------------------------
# Second run — same content, zero LLM calls, all cache hits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_run_skips_llm_for_unchanged_files(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "mod.py").write_text("def mod(): pass\n")
    run_cache: dict[str, FileSummary] = {}
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (_group_analysis("mod.py"), "", 10)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
            run_cache=run_cache,
        )
        result = await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
            run_cache=run_cache,
        )

    assert call_count == 1  # only from first run
    assert result["cache_hits"] == 1


# ---------------------------------------------------------------------------
# cache_hits counts files served from cache, not groups
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hits_counts_files_not_groups(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "a.py").write_text("def a(): pass\n")
    (tmp_path / "b.py").write_text("def b(): pass\n")
    run_cache: dict[str, FileSummary] = {}

    def _two_file_group() -> MagicMock:
        ea, eb = MagicMock(), MagicMock()
        ea.path, ea.summary, ea.key_symbols = "a.py", "A", []
        eb.path, eb.summary, eb.key_symbols = "b.py", "B", []
        group = MagicMock()
        group.files = [ea, eb]
        return group

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        return (_two_file_group(), "", 10)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
            run_cache=run_cache,
        )
        result = await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
            run_cache=run_cache,
        )

    assert result["cache_hits"] == 2


# ---------------------------------------------------------------------------
# Changed file content causes cache miss — LLM fires again for that file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_changed_file_content_causes_cache_miss(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    mod_file = tmp_path / "mod.py"
    mod_file.write_text("def original(): pass\n")
    run_cache: dict[str, FileSummary] = {}
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (_group_analysis("mod.py"), "", 5)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
            run_cache=run_cache,
        )
        assert call_count == 1

        mod_file.write_text("def changed(): return 42\n")
        result = await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
            run_cache=run_cache,
        )

    assert call_count == 2  # LLM fired again for changed file
    assert result["cache_hits"] == 0


# ---------------------------------------------------------------------------
# run_cache=None — no caching, LLM always fires (backward compat)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_cache_llm_fires_on_every_call(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "mod.py").write_text("def mod(): pass\n")
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (_group_analysis("mod.py"), "", 5)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
        )
        await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test",
        )

    assert call_count == 2  # no caching — fires every time
