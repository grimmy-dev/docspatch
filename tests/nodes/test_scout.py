"""Tests for scout node — parallel directory-grouped file analysis."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_group_analysis(path: str, summary: str, symbols: list[str]) -> MagicMock:
    entry = MagicMock()
    entry.path = path
    entry.summary = summary
    entry.key_symbols = symbols
    group = MagicMock()
    group.files = [entry]
    return group


def _make_llm_result(group_analysis: MagicMock, tokens: int = 5) -> tuple[MagicMock, str, int]:
    return (group_analysis, "", tokens)


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_file_summary_and_scout_output_are_importable() -> None:
    from src.schemas.scout_io import FileSummary, ScoutOutput

    summary: FileSummary = {"path": "src/foo.py", "summary": "Does foo.", "key_symbols": ["foo"]}
    output: ScoutOutput = {"summaries": [summary], "grouped": {}, "cache_hits": 0, "tokens_used": 5}
    assert output["tokens_used"] == 5
    assert summary["path"] == "src/foo.py"


# ---------------------------------------------------------------------------
# One LLM call per directory group
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scout_makes_one_llm_call_per_directory_group(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "foo.py").write_text("def foo(): pass\n")
    (tmp_path / "src" / "bar.py").write_text("def bar(): pass\n")
    (tmp_path / "tests" / "test_foo.py").write_text("def test_foo(): pass\n")

    group_a = _make_group_analysis("src/foo.py", "Foo module.", ["foo"])
    group_b = _make_group_analysis("tests/test_foo.py", "Tests for foo.", ["test_foo"])

    call_count = 0

    async def fake_llm(*_args: object, **_kwargs: object) -> tuple[MagicMock, str, int]:
        nonlocal call_count
        call_count += 1
        return (group_a if call_count == 1 else group_b, "", 5)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=fake_llm):
        result = await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test-model",
        )

    assert call_count == 2
    assert len(result["grouped"]) == 2


# ---------------------------------------------------------------------------
# AST compression exercised for real
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scout_prompt_contains_compressed_skeleton_not_raw_source(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    source = "def compute(x: int) -> int:\n    return x * 2\n"
    (tmp_path / "compute.py").write_text(source)

    captured_prompts: list[str] = []

    async def capturing_llm(_model: str, _system: str, prompt: str, **_kw: object) -> tuple[None, str, int]:
        captured_prompts.append(prompt)
        return (None, "", 0)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=capturing_llm):
        await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test-model",
        )

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    # Compressed skeleton keeps signature, strips body
    assert "def compute(x: int) -> int:" in prompt
    # Raw body (return statement) must not appear
    assert "return x * 2" not in prompt


# ---------------------------------------------------------------------------
# README mode: all Python files under target_path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scout_readme_mode_includes_all_python_files(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "alpha.py").write_text("def alpha(): pass\n")
    (tmp_path / "beta.py").write_text("def beta(): pass\n")

    captured_prompts: list[str] = []

    async def capturing_llm(_model: str, _system: str, prompt: str, **_kw: object) -> tuple[None, str, int]:
        captured_prompts.append(prompt)
        return (None, "", 0)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=capturing_llm):
        result = await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test-model",
        )

    all_prompt_text = "\n".join(captured_prompts)
    assert "alpha.py" in all_prompt_text
    assert "beta.py" in all_prompt_text
    _ = result


# ---------------------------------------------------------------------------
# CLG mode: only changed_files processed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scout_clg_mode_scopes_to_changed_files(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "changed.py").write_text("def changed(): pass\n")
    (tmp_path / "unchanged.py").write_text("def unchanged(): pass\n")

    captured_prompts: list[str] = []

    async def capturing_llm(_model: str, _system: str, prompt: str, **_kw: object) -> tuple[None, str, int]:
        captured_prompts.append(prompt)
        return (None, "", 0)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=capturing_llm):
        await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="clg",
            changed_files=["changed.py"],
            model_key="test-model",
        )

    all_prompt_text = "\n".join(captured_prompts)
    assert "changed.py" in all_prompt_text
    assert "unchanged.py" not in all_prompt_text


# ---------------------------------------------------------------------------
# Output schema shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scout_output_grouped_by_directory(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "utils.py").write_text("def util(): pass\n")

    group = _make_group_analysis("src/utils.py", "Utility functions.", ["util"])

    with patch("src.graph.nodes.scout.acall_llm", AsyncMock(return_value=(group, "", 3))):
        result = await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test-model",
        )

    assert "src" in result["grouped"]
    assert result["tokens_used"] == 3
    assert result["cache_hits"] == 0
    assert isinstance(result["summaries"], list)


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scout_returns_empty_when_cancelled(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / "foo.py").write_text("def foo(): pass\n")

    with patch("src.graph.nodes.scout.is_cancelled", return_value=True):
        result = await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test-model",
        )

    assert result["summaries"] == []
    assert result["grouped"] == {}
    assert result["tokens_used"] == 0


# ---------------------------------------------------------------------------
# Ignored directories excluded
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scout_excludes_ignored_directories(tmp_path: Path) -> None:
    from src.graph.nodes.scout import scout_node

    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "site.py").write_text("def _venv(): pass\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "real.py").write_text("def real(): pass\n")

    captured_prompts: list[str] = []

    async def capturing_llm(_model: str, _system: str, prompt: str, **_kw: object) -> tuple[None, str, int]:
        captured_prompts.append(prompt)
        return (None, "", 0)

    with patch("src.graph.nodes.scout.acall_llm", side_effect=capturing_llm):
        await scout_node(
            target_path=tmp_path,
            repo_root=tmp_path,
            mode="readme",
            model_key="test-model",
        )

    all_text = "\n".join(captured_prompts)
    assert "real.py" in all_text
    assert "site.py" not in all_text
