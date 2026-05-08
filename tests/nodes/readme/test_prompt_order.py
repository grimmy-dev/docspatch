"""Tests verifying build_readme_prompt section ordering — stable before dynamic."""

from pathlib import Path

from src.graph.nodes.readme.prompts import build_readme_prompt
from src.schemas.readme_io import ProjectContext
from src.schemas.readme_state import ReadmeState
from src.utils.git.reader import GitSignals

_SIGNALS = GitSignals(commit_count=42, first_commit="2022-01", last_commit="2026-04", is_dormant=False)


def _state(**kwargs: object) -> ReadmeState:
    return ReadmeState(**kwargs)  # type: ignore[arg-type]


def test_understanding_appears_before_git_signals() -> None:
    state = _state(project_understanding="summary text", git_signals=_SIGNALS)
    prompt = build_readme_prompt(state)
    assert prompt.index("summary text") < prompt.index("Git signals:")


def test_understanding_appears_before_existing_readme() -> None:
    state = _state(project_understanding="summary text", existing_readme="# Old README")
    prompt = build_readme_prompt(state)
    assert prompt.index("summary text") < prompt.index("# Old README")


def test_style_appears_after_understanding() -> None:
    state = _state(project_understanding="summary text", style="compact")
    prompt = build_readme_prompt(state)
    assert prompt.index("Style:") > prompt.index("summary text")


def test_style_appears_after_git_signals() -> None:
    state = _state(git_signals=_SIGNALS, style="compact")
    prompt = build_readme_prompt(state)
    assert prompt.index("Style:") > prompt.index("Git signals:")


def test_project_metadata_before_git_signals() -> None:
    state = _state(project_context=ProjectContext(name="myproj"), git_signals=_SIGNALS)
    prompt = build_readme_prompt(state)
    assert prompt.index("myproj") < prompt.index("Git signals:")


def test_remarks_at_tail() -> None:
    state = _state(project_context=ProjectContext(name="myproj"), git_signals=_SIGNALS, remarks="write short")
    prompt = build_readme_prompt(state)
    assert prompt.index("write short") > prompt.index("myproj")
    assert prompt.index("write short") > prompt.index("Git signals:")


def test_scope_label_present_in_output() -> None:
    state = _state(
        repo_root=Path("/repo"),
        target_path=Path("/repo"),
    )
    prompt = build_readme_prompt(state)
    assert "Scope: Project Root" in prompt


def test_public_api_fallback_when_no_understanding() -> None:
    state = _state(public_api={"src/foo.py": ["bar"]}, project_understanding=None)
    prompt = build_readme_prompt(state)
    assert "Public API" in prompt


def test_public_api_suppressed_when_understanding_present() -> None:
    state = _state(public_api={"src/foo.py": ["bar"]}, project_understanding="summary")
    prompt = build_readme_prompt(state)
    assert "Public API" not in prompt
