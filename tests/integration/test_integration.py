"""Integration tests — full graph pipelines with mocked acall_llm.

Verify that state flows correctly through each pipeline's node chain
and produces the expected interrupt at the user review stage.
Only acall_llm is mocked (the shell boundary); all other nodes run
against a real temp git repo so state-shape regressions surface here.
"""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.schemas.llm_outputs import BatchDocstringOutput, DocstringOutput


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Minimal git repo: two commits so diff-based pipelines have content."""

    def _git(*args: str) -> None:
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True)

    _git("init")
    _git("config", "user.email", "test@test.com")
    _git("config", "user.name", "Test")

    (tmp_path / "pyproject.toml").write_text('[project]\nname = "testpkg"\nversion = "0.1.0"\n')
    src = tmp_path / "src"
    src.mkdir()
    (src / "__init__.py").write_text("")
    (src / "main.py").write_text("def hello():\n    pass\n")
    _git("add", "-A")
    _git("commit", "-m", "initial commit")

    (src / "main.py").write_text("def hello():\n    pass\n\ndef world():\n    pass\n")
    _git("add", "-A")
    _git("commit", "-m", "add world function")

    return tmp_path


def _config(thread_id: str = "test") -> dict:
    return {"configurable": {"thread_id": thread_id}}


async def _first_interrupt(graph, state: dict, config: dict):
    """Stream graph and return the first interrupt value; None if graph completes without one."""
    async for event in graph.astream(state, config, stream_mode="updates"):
        if "__interrupt__" in event:
            return event["__interrupt__"][0].value
    return None


@pytest.mark.asyncio
async def test_docs_pipeline_interrupts_with_generated_docs(git_repo: Path) -> None:
    """Docs pipeline routes scanner → parser → significance → docwriter → review interrupt."""
    from langgraph.checkpoint.memory import MemorySaver

    from src.graph.graphs.docs_graph import build
    from src.schemas.state import DocpatchState

    graph = build(checkpointer=MemorySaver())
    state = DocpatchState(repo_path=git_repo, target_path=git_repo, update_all=True)

    mock_result = (
        BatchDocstringOutput(
            items=[
                DocstringOutput(name="hello", docstring="Says hello."),
                DocstringOutput(name="world", docstring="Says world."),
            ]
        ),
        "",
        10,
    )

    with patch("src.graph.nodes.docstring.docwriter.acall_llm", new_callable=AsyncMock, return_value=mock_result):
        interrupt_val = await _first_interrupt(graph, state.model_dump(), _config())

    assert interrupt_val is not None, "Expected review interrupt — graph completed early"
    assert interrupt_val["type"] == "review"
    assert interrupt_val["docs"], "generated_docs should be non-empty at review interrupt"


@pytest.mark.asyncio
async def test_clg_pipeline_interrupts_with_generated_entry(git_repo: Path) -> None:
    """CLG pipeline routes clg_context → clg_llm → changelog review interrupt."""
    from src.graph.graphs.clg_graph import build
    from src.schemas.changelog_state import ChangelogState

    graph = build()
    state = ChangelogState(repo_path=git_repo, from_ref="HEAD~1")

    with patch(
        "src.graph.nodes.changelog.generate.acall_llm",
        new_callable=AsyncMock,
        return_value=(None, "## v0.1.0\n\n- Added world function", 50),
    ):
        interrupt_val = await _first_interrupt(graph, state.model_dump(), _config())

    assert interrupt_val is not None, "Expected changelog review interrupt — graph completed early"
    assert interrupt_val["type"] == "clg_review"
    assert interrupt_val["content"], "generated_entry should be non-empty at review interrupt"


@pytest.mark.asyncio
async def test_readme_pipeline_interrupts_with_generated_readme(git_repo: Path) -> None:
    """README pipeline routes context → understand → llm → readme review interrupt."""
    from src.graph.graphs.readme_graph import build
    from src.schemas.readme_state import ReadmeState

    graph = build()
    state = ReadmeState(repo_path=git_repo, target_path=git_repo, rewrite=True)

    understand_mock = AsyncMock(return_value=(None, "A minimal test package.", 30))
    generate_mock = AsyncMock(return_value=(None, "# testpkg\n\nA test package.", 80))

    with (
        patch("src.graph.nodes.readme.understand.acall_llm", understand_mock),
        patch("src.graph.nodes.readme.generate.acall_llm", generate_mock),
    ):
        interrupt_val = await _first_interrupt(graph, state.model_dump(), _config())

    assert interrupt_val is not None, "Expected readme review interrupt — graph completed early"
    assert interrupt_val["type"] == "readme_review"
    assert interrupt_val["content"], "generated_readme should be non-empty at review interrupt"
