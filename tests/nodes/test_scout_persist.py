"""Tests for scout persistent cache integration (Issue 11).

All tests verify LLM call counts — the observable proxy for cache hit/miss behavior.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.schemas.scout_io import FileSummary


def _group_analysis(path: str, summary: str = "desc") -> MagicMock:
    entry = MagicMock()
    entry.path, entry.summary, entry.key_symbols = path, summary, []
    group = MagicMock()
    group.files = [entry]
    return group


# ---------------------------------------------------------------------------
# Tracer — second run, same content, zero LLM calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_run_unchanged_content_skips_llm(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "mod.py").write_text("def mod(): pass\n")
    scope_dir = tmp_path / "cache" / "scope"
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (_group_analysis("mod.py"), "", 5)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="test", scope_dir=scope_dir,
        )
        first_calls = call_count

        result = await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="test", scope_dir=scope_dir,
        )

    assert first_calls == 1
    assert call_count == 1  # second run: no new LLM calls
    assert result["cache_hits"] >= 1


# ---------------------------------------------------------------------------
# Second run — one file changed, exactly one LLM call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_second_run_one_changed_file_fires_one_llm_call(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    stable = tmp_path / "stable.py"
    changing = tmp_path / "changing.py"
    stable.write_text("def stable(): pass\n")
    changing.write_text("def original(): pass\n")
    scope_dir = tmp_path / "cache" / "scope"
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        group = MagicMock()
        ea, eb = MagicMock(), MagicMock()
        ea.path, ea.summary, ea.key_symbols = "stable.py", "Stable.", []
        eb.path, eb.summary, eb.key_symbols = "changing.py", "Changing.", []
        group.files = [ea, eb]
        return (group, "", 5)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="test", scope_dir=scope_dir,
        )
        first_calls = call_count

        changing.write_text("def updated(): return 42\n")
        await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="test", scope_dir=scope_dir,
        )

    assert first_calls == 1
    assert call_count == 2  # one more LLM call for the changed file


# ---------------------------------------------------------------------------
# Moved file — same content, new path: cache hit, no LLM call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_moved_file_gets_cache_hit(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    original = tmp_path / "original.py"
    original.write_text("def something(): pass\n")
    scope_dir = tmp_path / "cache" / "scope"
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (_group_analysis("original.py"), "", 5)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="test", scope_dir=scope_dir,
        )
        first_calls = call_count

        # Move file — same content, new path
        moved = tmp_path / "moved.py"
        moved.write_text("def something(): pass\n")
        original.unlink()

        result = await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="test", scope_dir=scope_dir,
        )

    assert first_calls == 1
    assert call_count == 1  # moved file hits cache — no new LLM call
    assert result["cache_hits"] >= 1


# ---------------------------------------------------------------------------
# Model name change — cache miss, LLM fires again
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_model_change_causes_cache_miss(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "mod.py").write_text("def mod(): pass\n")
    scope_dir = tmp_path / "cache" / "scope"
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (_group_analysis("mod.py"), "", 5)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="model-a", scope_dir=scope_dir,
        )
        first_calls = call_count

        await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="model-b", scope_dir=scope_dir,
        )

    assert first_calls == 1
    assert call_count == 2  # different model → cache miss → LLM fires


# ---------------------------------------------------------------------------
# No scope_dir — behaves exactly as before (backward compat)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_scope_dir_llm_fires_each_call(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "mod.py").write_text("def mod(): pass\n")
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (_group_analysis("mod.py"), "", 5)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="test",
        )
        await scout_node(
            target_path=tmp_path, repo_root=tmp_path,
            mode="readme", model_key="test",
        )

    assert call_count == 2
