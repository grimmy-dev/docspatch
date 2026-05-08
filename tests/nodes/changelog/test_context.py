"""Tests for clg_context node — all shell deps mocked."""

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.schemas.changelog_state import ChangelogState
from src.schemas.readme_io import ProjectContext

_MOD = "src.graph.nodes.changelog.context"


def _state(**kwargs: object) -> ChangelogState:
    return ChangelogState(**kwargs)  # type: ignore[arg-type]


def _mock_reader(
    *,
    root: Path = Path("/repo"),
    is_initial: bool = False,
    diff: str = "@@ some diff @@",
    changed_files: list[str] | None = None,
    commits: list[str] | None = None,
    initial_ctx: str = "",
) -> MagicMock:
    reader: MagicMock = MagicMock()
    reader.root = root
    reader.is_initial_commit.return_value = is_initial
    reader.get_diff.return_value = diff
    reader.get_diff_changed_files.return_value = changed_files if changed_files is not None else ["src/main.py"]
    reader.get_commit_log.return_value = commits if commits is not None else ["abc1234 feat: add thing"]
    reader.get_initial_commit_context.return_value = initial_ctx
    return reader


def _run(state: ChangelogState, reader: MagicMock | None = None, **overrides: object) -> dict:  # type: ignore[type-arg]
    if reader is None:
        reader = _mock_reader()
    mocks: dict[str, object] = {
        "GitReader": MagicMock(return_value=reader),
        "parse_pyproject": MagicMock(return_value=ProjectContext(version="1.2.3")),
        "filter_diff_noise": MagicMock(return_value={"content": "@@ some diff @@", "dropped_hunks": 0, "drop_reasons": []}),
        "score_and_filter_commits": MagicMock(side_effect=lambda c: c),
        "detect_breaking_changes": MagicMock(return_value=False),
    }
    mocks.update(overrides)
    with ExitStack() as stack:
        for name, mock in mocks.items():
            stack.enter_context(patch(f"{_MOD}.{name}", mock))
        from src.graph.nodes.changelog.context import clg_context

        return clg_context(state)


def test_normal_context_populates_all_fields() -> None:
    result = _run(_state())
    assert result["changed_files"] == ["src/main.py"]
    assert result["commits"] == ["abc1234 feat: add thing"]
    assert result["version"] == "1.2.3"
    assert result["is_initial_commit"] is False


def test_version_defaults_to_unreleased_when_none() -> None:
    result = _run(
        _state(),
        parse_pyproject=MagicMock(return_value=ProjectContext(version=None)),
    )
    assert result["version"] == "Unreleased"


def test_nothing_to_document_when_no_changed_files_and_no_commits() -> None:
    reader = _mock_reader(diff="", changed_files=[], commits=[])
    result = _run(_state(), reader=reader)
    assert result["nothing_to_document"] is True


def test_has_files_and_no_commits_is_not_nothing_to_document() -> None:
    reader = _mock_reader(changed_files=["src/main.py"], commits=[])
    result = _run(_state(), reader=reader)
    assert result["nothing_to_document"] is False


def test_has_breaking_changes_flag_propagated() -> None:
    result = _run(
        _state(),
        detect_breaking_changes=MagicMock(return_value=True),
    )
    assert result["has_breaking_changes"] is True


def test_initial_commit_sets_empty_changed_files_and_no_commits() -> None:
    reader = _mock_reader(is_initial=True, initial_ctx="README:\nMy Project\n\nFiles:\nsrc/main.py")
    result = _run(_state(), reader=reader)
    assert result["is_initial_commit"] is True
    assert result["changed_files"] == []
    assert result["commits"] == []
    assert result["has_breaking_changes"] is False
    assert result["nothing_to_document"] is False


def test_initial_commit_flag_ignored_when_from_ref_set() -> None:
    reader = _mock_reader(is_initial=True)
    result = _run(_state(from_ref="v0.1.0"), reader=reader)
    assert result["is_initial_commit"] is False


def test_raw_diff_not_stored_in_state() -> None:
    """Raw diff content must never end up in state — only changed_files list."""
    result = _run(_state())
    assert "diff" not in result


def test_nothing_to_document_false_when_commits_present_but_no_python_changes() -> None:
    reader = _mock_reader(changed_files=[], commits=["abc1234 docs: update README"])
    result = _run(_state(), reader=reader)
    assert result["nothing_to_document"] is False
