"""Tests for scanner node — mocks GitReader, verifies filtering."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.graph.nodes.docstring.scanner import scanner
from src.schemas.state import DocpatchState


def _state(repo_path: Path, from_ref: str | None = None) -> DocpatchState:
    return DocpatchState(repo_path=repo_path, target_path=repo_path, from_ref=from_ref)


def _mock_reader(root: Path, tracked: list[str], untracked: list[str] | None = None) -> MagicMock:
    reader: MagicMock = MagicMock()
    reader.root = root
    reader.resolve_target.return_value = root
    reader.list_committed_files.return_value = tracked
    reader.list_untracked_files.return_value = untracked or []
    return reader


def test_returns_only_python_files(tmp_path: Path) -> None:
    reader = _mock_reader(tmp_path, tracked=["src/foo.py", "src/readme.txt", "src/bar.py"])
    with patch("src.graph.nodes.docstring.scanner.GitReader", return_value=reader):
        result = scanner(_state(tmp_path))
    names = {p.name for p in result["changed_files"]}
    assert names == {"foo.py", "bar.py"}


def test_filters_ignored_paths(tmp_path: Path) -> None:
    reader = _mock_reader(tmp_path, tracked=["src/foo.py", "tests/test_foo.py"])
    with patch("src.graph.nodes.docstring.scanner.GitReader", return_value=reader):
        result = scanner(_state(tmp_path))
    names = {p.name for p in result["changed_files"]}
    assert "foo.py" in names
    assert "test_foo.py" not in names


def test_includes_untracked_python_files(tmp_path: Path) -> None:
    reader = _mock_reader(tmp_path, tracked=["src/a.py"], untracked=["src/b.py"])
    with patch("src.graph.nodes.docstring.scanner.GitReader", return_value=reader):
        result = scanner(_state(tmp_path))
    names = {p.name for p in result["changed_files"]}
    assert names == {"a.py", "b.py"}


def test_from_ref_passes_ref_to_list_committed_files(tmp_path: Path) -> None:
    reader = _mock_reader(tmp_path, tracked=["src/changed.py"])
    with patch("src.graph.nodes.docstring.scanner.GitReader", return_value=reader):
        result = scanner(_state(tmp_path, from_ref="v1.0.0"))
    reader.list_committed_files.assert_called_once_with(tmp_path, "v1.0.0")
    assert any(p.name == "changed.py" for p in result["changed_files"])


def test_empty_repo_returns_empty(tmp_path: Path) -> None:
    reader = _mock_reader(tmp_path, tracked=[], untracked=[])
    with patch("src.graph.nodes.docstring.scanner.GitReader", return_value=reader):
        result = scanner(_state(tmp_path))
    assert result["changed_files"] == []
