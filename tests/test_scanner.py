"""Tests for scanner node — mocks git shell layer, verifies filtering."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.graph.nodes.docstring.scanner import scanner
from src.schemas.state import DocpatchState


def _state(repo_path: Path, from_ref: str | None = None) -> DocpatchState:
    return DocpatchState(repo_path=repo_path, target_path=repo_path, from_ref=from_ref)


def _mock_repo(tracked: list[str], untracked: list[str] | None = None) -> MagicMock:
    repo: MagicMock = MagicMock()
    repo.git.ls_files.side_effect = lambda *args: "\n".join(tracked) if "--cached" in args else "\n".join(untracked or [])
    return repo


def test_returns_only_python_files(tmp_path: Path) -> None:
    repo = _mock_repo(tracked=["src/foo.py", "src/readme.txt", "src/bar.py"])
    # lazy fix for ruff checks line too long
    get_repo_path = "src.graph.nodes.docstring.scanner.get_repo"
    with patch(get_repo_path, return_value=repo), patch("src.graph.nodes.docstring.scanner.get_root", return_value=tmp_path):
        result = scanner(_state(tmp_path))
    names = {p.name for p in result["changed_files"]}
    assert names == {"foo.py", "bar.py"}


def test_filters_ignored_paths(tmp_path: Path) -> None:
    repo = _mock_repo(tracked=["src/foo.py", "tests/test_foo.py"])
    # lazy fix for ruff checks line too long
    get_repo_path = "src.graph.nodes.docstring.scanner.get_repo"
    with patch(get_repo_path, return_value=repo), patch("src.graph.nodes.docstring.scanner.get_root", return_value=tmp_path):
        result = scanner(_state(tmp_path))
    names = {p.name for p in result["changed_files"]}
    assert "foo.py" in names
    assert "test_foo.py" not in names


def test_includes_untracked_python_files(tmp_path: Path) -> None:
    repo = _mock_repo(tracked=["src/a.py"], untracked=["src/b.py"])
    # lazy fix for ruff checks line too long
    get_repo_path = "src.graph.nodes.docstring.scanner.get_repo"
    with patch(get_repo_path, return_value=repo), patch("src.graph.nodes.docstring.scanner.get_root", return_value=tmp_path):
        result = scanner(_state(tmp_path))
    names = {p.name for p in result["changed_files"]}
    assert names == {"a.py", "b.py"}


def test_from_ref_uses_diff_not_ls_files(tmp_path: Path) -> None:
    repo: MagicMock = MagicMock()
    repo.git.diff.return_value = "src/changed.py"
    repo.git.ls_files.return_value = ""
    # lazy fix for ruff checks line too long
    get_repo_path = "src.graph.nodes.docstring.scanner.get_repo"
    with patch(get_repo_path, return_value=repo), patch("src.graph.nodes.docstring.scanner.get_root", return_value=tmp_path):
        result = scanner(_state(tmp_path, from_ref="v1.0.0"))
    repo.git.diff.assert_called_once()
    assert any(p.name == "changed.py" for p in result["changed_files"])


def test_empty_repo_returns_empty(tmp_path: Path) -> None:
    repo = _mock_repo(tracked=[], untracked=[])
    # lazy fix for ruff checks line too long
    get_repo_path = "src.graph.nodes.docstring.scanner.get_repo"
    with patch(get_repo_path, return_value=repo), patch("src.graph.nodes.docstring.scanner.get_root", return_value=tmp_path):
        result = scanner(_state(tmp_path))
    assert result["changed_files"] == []
