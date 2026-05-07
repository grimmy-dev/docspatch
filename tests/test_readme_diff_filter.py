"""Tests for readme_diff_filter — all routing branches covered."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.schemas.readme_state import ReadmeState

_MEANINGFUL_DIFF = (
    "diff --git a/src/foo.py b/src/foo.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def foo():\n"
    "-    return 1\n"
    "+    return 2\n"
)

_NOISE_DIFF = (
    "diff --git a/src/foo.py b/src/foo.py\n"
    "@@ -1,1 +1,1 @@\n"
    "+  # a comment\n"
)


def _state(**kwargs: object) -> ReadmeState:
    return ReadmeState(repo_path=Path("/repo"), target_path=Path("/repo"), **kwargs)  # type: ignore[arg-type]


def _patch_deps(repo: MagicMock, changed: list[str]) -> list[object]:
    return [
        patch("src.graph.nodes.readme.diff_filter.get_repo", return_value=repo),
        patch("src.graph.nodes.readme.diff_filter.get_diff_files", return_value=changed),
    ]


def test_rewrite_flag_bypasses_filter() -> None:
    from src.graph.nodes.readme.diff_filter import readme_diff_filter

    assert readme_diff_filter(_state(rewrite=True)) == {}


def test_no_changes_with_existing_readme_sets_up_to_date() -> None:
    from src.graph.nodes.readme.diff_filter import readme_diff_filter

    patches = _patch_deps(MagicMock(), [])
    with patches[0], patches[1]:
        result = readme_diff_filter(_state(existing_readme="# Existing"))

    assert result == {"up_to_date": True}


def test_no_changes_without_readme_returns_empty() -> None:
    from src.graph.nodes.readme.diff_filter import readme_diff_filter

    patches = _patch_deps(MagicMock(), [])
    with patches[0], patches[1]:
        result = readme_diff_filter(_state(existing_readme=None))

    assert result == {}


def test_changed_files_with_existing_readme_sets_diff_files() -> None:
    from src.graph.nodes.readme.diff_filter import readme_diff_filter

    repo = MagicMock()
    repo.git.diff.return_value = _MEANINGFUL_DIFF
    changed = ["src/foo.py"]
    patches = _patch_deps(repo, changed)
    with patches[0], patches[1]:
        result = readme_diff_filter(_state(existing_readme="# Existing"))

    assert result == {"diff_changed_files": changed}


def test_changed_files_without_readme_returns_empty() -> None:
    from src.graph.nodes.readme.diff_filter import readme_diff_filter

    patches = _patch_deps(MagicMock(), ["src/foo.py"])
    with patches[0], patches[1]:
        result = readme_diff_filter(_state(existing_readme=None))

    assert result == {}


def test_repo_not_found_returns_empty() -> None:
    from src.graph.nodes.readme.diff_filter import readme_diff_filter

    with patch("src.graph.nodes.readme.diff_filter.get_repo", side_effect=Exception("no git")):
        result = readme_diff_filter(_state(existing_readme="# Existing"))

    assert result == {}


def test_noise_only_changes_set_up_to_date() -> None:
    from src.graph.nodes.readme.diff_filter import readme_diff_filter

    repo = MagicMock()
    repo.git.diff.return_value = _NOISE_DIFF
    patches = _patch_deps(repo, ["src/foo.py"])
    with patches[0], patches[1]:
        result = readme_diff_filter(_state(existing_readme="# Existing"))

    assert result == {"up_to_date": True}


def test_noise_check_failure_falls_back_to_diff_changed_files() -> None:
    from src.graph.nodes.readme.diff_filter import readme_diff_filter

    repo = MagicMock()
    repo.git.diff.side_effect = Exception("git failure")
    changed = ["src/foo.py"]
    patches = _patch_deps(repo, changed)
    with patches[0], patches[1]:
        result = readme_diff_filter(_state(existing_readme="# Existing"))

    assert result == {"diff_changed_files": changed}
