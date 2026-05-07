"""Tests for changelog_git — shell functions tested via mocks and tmp_path."""

from pathlib import Path
from unittest.mock import MagicMock

from src.utils.git.changelog import (
    get_commit_log,
    get_git_diff,
    get_initial_commit_context,
    is_initial_commit,
)


def _repo(diff: str = "", log: str = "", rev_count: str = "5", ls: str = "") -> MagicMock:
    repo: MagicMock = MagicMock()
    repo.git.diff.return_value = diff
    repo.git.log.return_value = log
    repo.git.rev_list.return_value = rev_count
    repo.git.ls_files.return_value = ls
    return repo


# ---------------------------------------------------------------------------
# get_git_diff
# ---------------------------------------------------------------------------


def test_working_tree_diff_calls_diff_head() -> None:
    repo = _repo(diff="@@ some diff @@")
    result = get_git_diff(repo, from_ref=None, to_ref=None)
    repo.git.diff.assert_called_once()
    call_args = repo.git.diff.call_args[0]
    assert call_args[0] == "HEAD"
    assert result == "@@ some diff @@"


def test_ref_range_uses_dotdot_notation() -> None:
    repo = _repo(diff="@@ range diff @@")
    get_git_diff(repo, from_ref="v1.0.0", to_ref=None)
    call_args = repo.git.diff.call_args[0]
    assert call_args[0] == "v1.0.0..HEAD"


def test_custom_to_ref_included_in_range() -> None:
    repo = _repo()
    get_git_diff(repo, from_ref="v1.0.0", to_ref="v1.1.0")
    call_args = repo.git.diff.call_args[0]
    assert call_args[0] == "v1.0.0..v1.1.0"


def test_get_git_diff_returns_empty_on_exception() -> None:
    repo: MagicMock = MagicMock()
    repo.git.diff.side_effect = Exception("bad ref")
    assert get_git_diff(repo, from_ref="bad", to_ref=None) == ""


def test_noise_pathspecs_passed_to_diff() -> None:
    repo = _repo()
    get_git_diff(repo, from_ref=None, to_ref=None)
    call_args = repo.git.diff.call_args[0]
    assert any(":(exclude)" in arg for arg in call_args)


# ---------------------------------------------------------------------------
# get_commit_log
# ---------------------------------------------------------------------------


def test_commit_log_returns_empty_when_no_from_ref() -> None:
    repo = _repo(log="a1b2c3d feat: something")
    assert get_commit_log(repo, from_ref=None, to_ref=None) == []
    repo.git.log.assert_not_called()


def test_commit_log_returns_formatted_entries() -> None:
    repo = _repo(log="a1b2c3d feat: add filter\ne4f5g6h fix: edge case")
    result = get_commit_log(repo, from_ref="v1.0.0", to_ref=None)
    assert result == ["a1b2c3d feat: add filter", "e4f5g6h fix: edge case"]


def test_commit_log_handles_bytes_output() -> None:
    repo: MagicMock = MagicMock()
    repo.git.log.return_value = b"a1b2c3d feat: bytes msg"
    result = get_commit_log(repo, from_ref="v1.0.0", to_ref=None)
    assert result == ["a1b2c3d feat: bytes msg"]


def test_commit_log_handles_bytearray_output() -> None:
    repo: MagicMock = MagicMock()
    repo.git.log.return_value = bytearray(b"a1b2c3d fix: bytearray msg")
    result = get_commit_log(repo, from_ref="v1.0.0", to_ref=None)
    assert result == ["a1b2c3d fix: bytearray msg"]


def test_commit_log_returns_empty_on_exception() -> None:
    repo: MagicMock = MagicMock()
    repo.git.log.side_effect = Exception("git error")
    assert get_commit_log(repo, from_ref="v1.0.0", to_ref=None) == []


# ---------------------------------------------------------------------------
# is_initial_commit
# ---------------------------------------------------------------------------


def test_is_initial_commit_true_when_count_one() -> None:
    assert is_initial_commit(_repo(rev_count="1")) is True


def test_is_initial_commit_false_when_multiple_commits() -> None:
    assert is_initial_commit(_repo(rev_count="42")) is False


def test_is_initial_commit_false_on_exception() -> None:
    repo: MagicMock = MagicMock()
    repo.git.rev_list.side_effect = Exception("no HEAD")
    assert is_initial_commit(repo) is False


# ---------------------------------------------------------------------------
# get_initial_commit_context
# ---------------------------------------------------------------------------


def test_initial_context_includes_readme(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# My Project\nA cool tool.")
    repo = _repo(ls="src/main.py\nsrc/utils.py")
    result = get_initial_commit_context(repo, tmp_path)
    assert "README:" in result
    assert "My Project" in result


def test_initial_context_includes_ls_files(tmp_path: Path) -> None:
    repo = _repo(ls="src/main.py\nsrc/utils.py")
    result = get_initial_commit_context(repo, tmp_path)
    assert "Files:" in result
    assert "src/main.py" in result


def test_initial_context_skips_missing_readme(tmp_path: Path) -> None:
    repo = _repo(ls="src/main.py")
    result = get_initial_commit_context(repo, tmp_path)
    assert "README:" not in result
    assert "Files:" in result
