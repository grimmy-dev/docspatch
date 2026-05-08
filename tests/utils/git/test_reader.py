"""Tests for GitReader — all gitpython calls mocked at the repo level."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.git.reader import GitReader, GitSignals


def _make_reader(mock_repo: MagicMock, root: Path = Path("/repo")) -> GitReader:

    mock_repo.working_tree_dir = str(root)
    with patch("src.utils.git.reader.get_repo", return_value=mock_repo):
        return GitReader()


def _repo() -> MagicMock:
    return MagicMock()


# ---------------------------------------------------------------------------
# get_diff_files
# ---------------------------------------------------------------------------


def test_get_diff_files_returns_py_files(tmp_path: Path) -> None:
    repo = _repo()
    repo.git.diff.return_value = "src/foo.py\nsrc/bar.py\n"
    reader = _make_reader(repo, tmp_path)
    assert reader.get_diff_files(tmp_path) == ["src/foo.py", "src/bar.py"]


def test_get_diff_files_filters_non_py_files(tmp_path: Path) -> None:
    repo = _repo()
    repo.git.diff.return_value = "src/foo.py\nREADME.md\nsrc/bar.ts\n"
    reader = _make_reader(repo, tmp_path)
    assert reader.get_diff_files(tmp_path) == ["src/foo.py"]


def test_get_diff_files_returns_empty_on_exception(tmp_path: Path) -> None:
    repo = _repo()
    repo.git.diff.side_effect = Exception("git error")
    reader = _make_reader(repo, tmp_path)
    assert reader.get_diff_files(tmp_path) == []


# ---------------------------------------------------------------------------
# get_activity_signals
# ---------------------------------------------------------------------------


def test_get_activity_signals_returns_struct() -> None:
    repo = _repo()
    repo.git.rev_list.return_value = "42"
    repo.git.log.side_effect = ["2026-04-01", "2022-01-01"]
    reader = _make_reader(repo)
    with patch("src.utils.git.reader.datetime") as mock_dt:
        mock_dt.strptime.side_effect = datetime.strptime
        mock_dt.now.return_value = datetime(2026, 5, 1)
        result = reader.get_activity_signals()
    assert isinstance(result, GitSignals)
    assert result.commit_count == 42
    assert result.first_commit == "2022-01"
    assert result.last_commit == "2026-04"
    assert result.is_dormant is False


def test_get_activity_signals_dormant_when_stale() -> None:
    repo = _repo()
    repo.git.rev_list.return_value = "5"
    repo.git.log.side_effect = ["2023-01-01", "2020-01-01"]
    reader = _make_reader(repo)
    with patch("src.utils.git.reader.datetime") as mock_dt:
        mock_dt.strptime.side_effect = datetime.strptime
        mock_dt.now.return_value = datetime(2026, 5, 1)
        result = reader.get_activity_signals()
    assert result is not None
    assert result.is_dormant is True


def test_get_activity_signals_returns_none_on_exception() -> None:
    repo = _repo()
    repo.git.rev_list.side_effect = Exception("git error")
    reader = _make_reader(repo)
    assert reader.get_activity_signals() is None


# ---------------------------------------------------------------------------
# get_remote_url
# ---------------------------------------------------------------------------


def test_get_remote_url_returns_first_remote() -> None:
    repo = _repo()
    remote = MagicMock()
    remote.url = "git@github.com:user/repo.git"
    repo.remotes = [remote]
    reader = _make_reader(repo)
    assert reader.get_remote_url() == "git@github.com:user/repo.git"


def test_get_remote_url_returns_none_when_no_remotes() -> None:
    repo = _repo()
    repo.remotes = []
    reader = _make_reader(repo)
    assert reader.get_remote_url() is None


# ---------------------------------------------------------------------------
# list_committed_files
# ---------------------------------------------------------------------------


def test_list_committed_files_uses_ls_files_without_from_ref(tmp_path: Path) -> None:
    repo = _repo()
    repo.git.ls_files.return_value = "src/a.py\nsrc/b.py"
    reader = _make_reader(repo, tmp_path)
    result = reader.list_committed_files(tmp_path, from_ref=None)
    repo.git.ls_files.assert_called_once_with("--cached", str(tmp_path))
    assert result == ["src/a.py", "src/b.py"]


def test_list_committed_files_uses_diff_with_from_ref(tmp_path: Path) -> None:
    repo = _repo()
    repo.git.diff.return_value = "src/changed.py"
    reader = _make_reader(repo, tmp_path)
    result = reader.list_committed_files(tmp_path, from_ref="v1.0.0")
    call_args = repo.git.diff.call_args[0]
    assert "--name-only" in call_args
    assert "v1.0.0" in call_args
    assert result == ["src/changed.py"]


# ---------------------------------------------------------------------------
# list_untracked_files
# ---------------------------------------------------------------------------


def test_list_untracked_files_returns_paths(tmp_path: Path) -> None:
    repo = _repo()
    repo.git.ls_files.return_value = "src/new.py"
    reader = _make_reader(repo, tmp_path)
    result = reader.list_untracked_files(tmp_path)
    call_args = repo.git.ls_files.call_args[0]
    assert "--others" in call_args
    assert result == ["src/new.py"]


# ---------------------------------------------------------------------------
# get_raw_diff
# ---------------------------------------------------------------------------


def test_get_raw_diff_without_target() -> None:
    repo = _repo()
    repo.git.diff.return_value = "@@ diff @@"
    reader = _make_reader(repo)
    result = reader.get_raw_diff()
    call_args = repo.git.diff.call_args[0]
    assert call_args == ("HEAD", "--")
    assert result == "@@ diff @@"


def test_get_raw_diff_with_target(tmp_path: Path) -> None:
    repo = _repo()
    repo.git.diff.return_value = "@@ scoped diff @@"
    reader = _make_reader(repo, tmp_path)
    result = reader.get_raw_diff(tmp_path)
    call_args = repo.git.diff.call_args[0]
    assert str(tmp_path) in call_args
    assert result == "@@ scoped diff @@"


def test_get_raw_diff_returns_empty_on_exception() -> None:
    repo = _repo()
    repo.git.diff.side_effect = Exception("git error")
    reader = _make_reader(repo)
    assert reader.get_raw_diff() == ""
