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
    commits: list[str] | None = None,
    initial_ctx: str = "",
) -> MagicMock:
    reader: MagicMock = MagicMock()
    reader.root = root
    reader.is_initial_commit.return_value = is_initial
    reader.get_diff.return_value = diff
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
        "truncate_diff": MagicMock(return_value=("@@ some diff @@", False)),
        "detect_breaking_changes": MagicMock(return_value=False),
        "load": MagicMock(return_value=MagicMock(defaults=MagicMock(changelog_diff_cap=8000))),
    }
    mocks.update(overrides)
    with ExitStack() as stack:
        for name, mock in mocks.items():
            stack.enter_context(patch(f"{_MOD}.{name}", mock))
        from src.graph.nodes.changelog.context import clg_context

        return clg_context(state)


def test_normal_diff_populates_all_fields() -> None:
    result = _run(_state())
    assert result["diff"] == "@@ some diff @@"
    assert result["commits"] == ["abc1234 feat: add thing"]
    assert result["version"] == "1.2.3"
    assert result["is_initial_commit"] is False
    assert result["diff_was_truncated"] is False


def test_version_defaults_to_unreleased_when_none() -> None:
    result = _run(
        _state(),
        parse_pyproject=MagicMock(return_value=ProjectContext(version=None)),
    )
    assert result["version"] == "Unreleased"


def test_nothing_to_document_when_empty_diff_and_no_commits() -> None:
    reader = _mock_reader(diff="", commits=[])
    result = _run(
        _state(),
        reader=reader,
        filter_diff_noise=MagicMock(return_value={"content": "", "dropped_hunks": 0, "drop_reasons": []}),
        truncate_diff=MagicMock(return_value=("", False)),
    )
    assert result["nothing_to_document"] is True


def test_diff_was_truncated_flag_propagated() -> None:
    result = _run(
        _state(),
        truncate_diff=MagicMock(return_value=("short diff", True)),
    )
    assert result["diff_was_truncated"] is True


def test_has_breaking_changes_flag_propagated() -> None:
    result = _run(
        _state(),
        detect_breaking_changes=MagicMock(return_value=True),
    )
    assert result["has_breaking_changes"] is True


def test_initial_commit_returns_context_payload() -> None:
    ctx = "README:\nMy Project\n\nFiles:\nsrc/main.py"
    reader = _mock_reader(is_initial=True, initial_ctx=ctx)
    result = _run(_state(), reader=reader)
    assert result["is_initial_commit"] is True
    assert result["diff"] == ctx
    assert result["commits"] == []
    assert result["has_breaking_changes"] is False


def test_initial_commit_flag_ignored_when_from_ref_set() -> None:
    reader = _mock_reader(is_initial=True)
    result = _run(_state(from_ref="v0.1.0"), reader=reader)
    assert result["is_initial_commit"] is False
