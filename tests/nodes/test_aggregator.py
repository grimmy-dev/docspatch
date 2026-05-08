"""Tests for aggregator node — unified context document from scout grouped output."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.schemas.scout_io import FileSummary


def _summary(path: str, summary: str, symbols: list[str] | None = None) -> FileSummary:
    return FileSummary(path=path, summary=summary, key_symbols=symbols or [])


# ---------------------------------------------------------------------------
# Tracer bullet — returns a string, one LLM call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregator_returns_llm_output_string() -> None:
    from src.graph.nodes.aggregator import aggregator_node

    grouped = {"src": [_summary("src/foo.py", "Foo module.", ["foo"])]}
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[None, str, int]:
        nonlocal call_count
        call_count += 1
        return (None, "Unified context.", 10)

    with patch("src.graph.nodes.aggregator.acall_llm", side_effect=fake_llm):
        result = await aggregator_node(grouped=grouped, model_key="test")

    assert call_count == 1
    assert result == "Unified context."


# ---------------------------------------------------------------------------
# Concat includes directory section headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregator_prompt_includes_directory_headers() -> None:
    from src.graph.nodes.aggregator import aggregator_node

    grouped = {
        "src/utils": [_summary("src/utils/fs.py", "Filesystem helpers.", ["hash_file"])],
        "src/cli": [_summary("src/cli/main.py", "CLI entrypoint.", ["app"])],
    }
    captured: list[str] = []

    async def capturing_llm(_model: str, _system: str, prompt: str, **_kw: object) -> tuple[None, str, int]:
        captured.append(prompt)
        return (None, "ok", 5)

    with patch("src.graph.nodes.aggregator.acall_llm", side_effect=capturing_llm):
        await aggregator_node(grouped=grouped, model_key="test")

    assert len(captured) == 1
    assert "src/utils" in captured[0]
    assert "src/cli" in captured[0]


# ---------------------------------------------------------------------------
# Concat includes file summary lines under each section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregator_prompt_includes_file_summaries() -> None:
    from src.graph.nodes.aggregator import aggregator_node

    grouped = {
        "src": [
            _summary("src/foo.py", "Handles foo logic.", ["Foo", "foo_fn"]),
            _summary("src/bar.py", "Handles bar logic.", ["Bar"]),
        ]
    }
    captured: list[str] = []

    async def capturing_llm(_model: str, _system: str, prompt: str, **_kw: object) -> tuple[None, str, int]:
        captured.append(prompt)
        return (None, "ok", 5)

    with patch("src.graph.nodes.aggregator.acall_llm", side_effect=capturing_llm):
        await aggregator_node(grouped=grouped, model_key="test")

    assert "Handles foo logic." in captured[0]
    assert "Handles bar logic." in captured[0]


# ---------------------------------------------------------------------------
# Empty grouped → empty string, no LLM call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregator_empty_grouped_returns_empty_string_without_llm_call() -> None:
    from src.graph.nodes.aggregator import aggregator_node

    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[None, str, int]:
        nonlocal call_count
        call_count += 1
        return (None, "should not be called", 0)

    with patch("src.graph.nodes.aggregator.acall_llm", side_effect=fake_llm):
        result = await aggregator_node(grouped={}, model_key="test")

    assert result == ""
    assert call_count == 0


# ---------------------------------------------------------------------------
# Exactly one LLM call regardless of number of directories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aggregator_makes_exactly_one_llm_call_for_many_directories() -> None:
    from src.graph.nodes.aggregator import aggregator_node

    grouped = {
        f"dir{i}": [_summary(f"dir{i}/mod.py", f"Module {i}.", [])]
        for i in range(5)
    }
    call_count = 0

    async def fake_llm(*_a: object, **_kw: object) -> tuple[None, str, int]:
        nonlocal call_count
        call_count += 1
        return (None, "combined", 20)

    with patch("src.graph.nodes.aggregator.acall_llm", side_effect=fake_llm):
        await aggregator_node(grouped=grouped, model_key="test")

    assert call_count == 1
