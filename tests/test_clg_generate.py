"""Tests for build_clg_prompt — pure function, no mocking required."""

from src.graph.nodes.changelog.generate import build_clg_prompt
from src.schemas.changelog_state import ChangelogState


def _state(**kwargs: object) -> ChangelogState:
    return ChangelogState(**kwargs)  # type: ignore[arg-type]


def test_version_in_prompt() -> None:
    assert "2.1.0" in build_clg_prompt(_state(version="2.1.0"))


def test_range_with_from_ref_only() -> None:
    result = build_clg_prompt(_state(from_ref="v1.0.0"))
    assert "v1.0.0..HEAD" in result


def test_range_with_from_and_to_ref() -> None:
    result = build_clg_prompt(_state(from_ref="v1.0.0", to_ref="v1.1.0"))
    assert "v1.0.0..v1.1.0" in result


def test_range_without_from_ref_says_working_tree() -> None:
    assert "working tree" in build_clg_prompt(_state())


def test_commits_listed_in_prompt() -> None:
    result = build_clg_prompt(_state(commits=["abc1234 feat: add filter", "e4f5g6h fix: edge case"]))
    assert "abc1234 feat: add filter" in result
    assert "e4f5g6h fix: edge case" in result


def test_no_commits_section_when_empty() -> None:
    result = build_clg_prompt(_state(commits=[]))
    assert "Commits:" not in result


def test_breaking_changes_instruction_present_when_flagged() -> None:
    result = build_clg_prompt(_state(has_breaking_changes=True))
    assert "Breaking" in result


def test_breaking_changes_absent_when_not_flagged() -> None:
    result = build_clg_prompt(_state(has_breaking_changes=False))
    assert "BREAKING" not in result.upper() or "Breaking Changes" not in result


def test_initial_release_instruction_present() -> None:
    assert "Initial" in build_clg_prompt(_state(is_initial_commit=True))


def test_diff_included_in_prompt() -> None:
    assert "@@ some changes @@" in build_clg_prompt(_state(diff="@@ some changes @@"))


def test_initial_commit_labels_payload_as_project_context() -> None:
    result = build_clg_prompt(_state(is_initial_commit=True, diff="README:\nMy Project"))
    assert "Project context" in result
    assert "Diff:" not in result


def test_normal_diff_labelled_as_diff() -> None:
    result = build_clg_prompt(_state(is_initial_commit=False, diff="@@ changed @@"))
    assert "Diff:" in result


def test_style_note_in_prompt() -> None:
    assert "Style:" in build_clg_prompt(_state(style="compact"))
