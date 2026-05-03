"""Tests for docwriter nodes — mocks acall_llm, verifies fan-out and rerun logic."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from conftest import make_catalog, make_fn

from src.schemas.llm_outputs import BatchDocstringOutput, DocstringOutput
from src.schemas.state import DocpatchState


def _state(**kwargs: object) -> DocpatchState:
    fn_a = make_fn("alpha", file_path="src/mod.py", start_line=1, end_line=5)
    fn_b = make_fn("beta", file_path="src/mod.py", start_line=6, end_line=10)
    ids, catalog = make_catalog(fn_a, fn_b)
    return DocpatchState(
        repo_path=Path("/repo"),
        target_path=Path("/repo"),
        catalog=catalog,
        current_batch=ids,
        rerun_docs=ids,
        **kwargs,  # type: ignore[arg-type]
    )


def _llm_result(*names: str, tokens: int = 10) -> tuple[BatchDocstringOutput, str, int]:
    return BatchDocstringOutput(items=[DocstringOutput(name=n, docstring=f"Doc for {n}.") for n in names]), "", tokens


@pytest.mark.asyncio
async def test_docwriter_single_calls_llm_once() -> None:
    from src.graph.nodes.docstring.docwriter import docwriter_single

    state = _state()
    mock_result = _llm_result("alpha", "beta")

    with patch("src.graph.nodes.docstring.docwriter.acall_llm", new_callable=AsyncMock, return_value=mock_result):
        result = await docwriter_single(state.model_dump())

    assert len(result["generated_docs"]) == 2


@pytest.mark.asyncio
async def test_docwriter_single_partial_failure() -> None:
    """LLM returns doc for only one function — missing one is absent from output."""
    from src.graph.nodes.docstring.docwriter import docwriter_single

    state = _state()
    mock_result = _llm_result("alpha")  # beta missing

    with patch("src.graph.nodes.docstring.docwriter.acall_llm", new_callable=AsyncMock, return_value=mock_result):
        result = await docwriter_single(state.model_dump())

    alpha_id = next(k for k, v in state.catalog.items() if v.name == "alpha")
    beta_id = next(k for k, v in state.catalog.items() if v.name == "beta")
    assert alpha_id in result["generated_docs"]
    assert beta_id not in result["generated_docs"]


@pytest.mark.asyncio
async def test_docwriter_single_skips_on_dry_run() -> None:
    from src.graph.nodes.docstring.docwriter import docwriter_single

    state = _state(dry_run=True)

    with patch("src.graph.nodes.docstring.docwriter.acall_llm", new_callable=AsyncMock) as mock_llm:
        result = await docwriter_single(state.model_dump())

    mock_llm.assert_not_called()
    assert result["generated_docs"] == {}


@pytest.mark.asyncio
async def test_docwriter_rerun_calls_llm_per_function() -> None:
    """One acall_llm call per function in rerun_docs."""
    from src.graph.nodes.docstring.docwriter import docwriter_rerun

    fn_a = make_fn("alpha", file_path="src/mod.py")
    fn_b = make_fn("beta", file_path="src/mod.py")
    ids, catalog = make_catalog(fn_a, fn_b)
    state = DocpatchState(repo_path=Path("/repo"), target_path=Path("/repo"), catalog=catalog, rerun_docs=ids)

    async def _side_effect(*_: object, **__: object) -> tuple[BatchDocstringOutput, str, int]:
        return _llm_result("alpha", "beta")

    with patch("src.graph.nodes.docstring.docwriter.acall_llm", new_callable=AsyncMock, side_effect=_side_effect) as mock_llm:
        result = await docwriter_rerun(state.model_dump())

    assert mock_llm.call_count == 2
    assert len(result["generated_docs"]) == 2


@pytest.mark.asyncio
async def test_docwriter_rerun_partial_failure() -> None:
    """When one LLM call returns no items, only the successful one is in output."""
    from src.graph.nodes.docstring.docwriter import docwriter_rerun

    state = _state()
    call_count = 0

    async def _side_effect(*_: object, **__: object) -> tuple[BatchDocstringOutput, str, int]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return BatchDocstringOutput(items=[DocstringOutput(name="alpha", docstring="Doc.")]), "", 5
        return BatchDocstringOutput(items=[]), "", 0

    with patch("src.graph.nodes.docstring.docwriter.acall_llm", new_callable=AsyncMock, side_effect=_side_effect):
        result = await docwriter_rerun(state.model_dump())

    assert len(result["generated_docs"]) == 1
    alpha_id = next(k for k, v in state.catalog.items() if v.name == "alpha")
    assert alpha_id in result["generated_docs"]
