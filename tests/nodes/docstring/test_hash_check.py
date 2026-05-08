"""Tests for hash_check nodes — cache hit/miss behaviour for files and functions."""

from pathlib import Path
from unittest.mock import patch

from conftest import make_catalog, make_fn

from src.schemas.state import DocpatchState


def _file_state(paths: list[Path]) -> DocpatchState:
    return DocpatchState(repo_path=Path("/repo"), target_path=Path("/repo"), changed_files=paths)


def _fn_state(**kwargs: object) -> DocpatchState:
    fn_a = make_fn("alpha", body_hash="hash_a")
    fn_b = make_fn("beta", body_hash="hash_b")
    _, catalog = make_catalog(fn_a, fn_b)
    return DocpatchState(repo_path=Path("/repo"), target_path=Path("/repo"), catalog=catalog, **kwargs)  # type: ignore[arg-type]


# ── file_hash_check ──────────────────────────────────────────────────────────


def test_file_hash_check_keeps_changed_file() -> None:
    from src.graph.nodes.docstring.hash_check import file_hash_check

    path = Path("/repo/src/foo.py")
    with (
        patch("src.graph.nodes.docstring.hash_check.hash_file", return_value="new_hash"),
        patch("src.graph.nodes.docstring.hash_check.get_file_hash", return_value="old_hash"),
    ):
        result = file_hash_check(_file_state([path]))

    assert path in result["changed_files"]


def test_file_hash_check_excludes_unchanged_file() -> None:
    from src.graph.nodes.docstring.hash_check import file_hash_check

    path = Path("/repo/src/foo.py")
    with (
        patch("src.graph.nodes.docstring.hash_check.hash_file", return_value="same_hash"),
        patch("src.graph.nodes.docstring.hash_check.get_file_hash", return_value="same_hash"),
    ):
        result = file_hash_check(_file_state([path]))

    assert path not in result["changed_files"]


def test_file_hash_check_includes_uncached_file() -> None:
    from src.graph.nodes.docstring.hash_check import file_hash_check

    path = Path("/repo/src/new.py")
    with (
        patch("src.graph.nodes.docstring.hash_check.hash_file", return_value="some_hash"),
        patch("src.graph.nodes.docstring.hash_check.get_file_hash", return_value=None),
    ):
        result = file_hash_check(_file_state([path]))

    assert path in result["changed_files"]


def test_file_hash_check_skips_unreadable_file() -> None:
    from src.graph.nodes.docstring.hash_check import file_hash_check

    path = Path("/repo/src/missing.py")
    with (
        patch("src.graph.nodes.docstring.hash_check.hash_file", return_value=None),
        patch("src.graph.nodes.docstring.hash_check.get_file_hash", return_value=None),
    ):
        result = file_hash_check(_file_state([path]))

    assert path not in result["changed_files"]


# ── function_hash_check ──────────────────────────────────────────────────────


def test_function_hash_check_marks_changed_function_significant() -> None:
    from src.graph.nodes.docstring.hash_check import function_hash_check

    state = _fn_state()
    with patch("src.graph.nodes.docstring.hash_check.get_function_hash", return_value="old_hash"):
        result = function_hash_check(state)

    for fn in result["catalog"].values():
        assert fn.is_significant


def test_function_hash_check_skips_unchanged_function() -> None:
    from src.graph.nodes.docstring.hash_check import function_hash_check

    fn_a = make_fn("alpha", body_hash="hash_a")
    fn_b = make_fn("beta", body_hash="hash_b")
    _, catalog = make_catalog(fn_a, fn_b)
    state = DocpatchState(repo_path=Path("/repo"), target_path=Path("/repo"), catalog=catalog)

    def _cached(path: Path, name: str) -> str | None:
        return {"alpha": "hash_a", "beta": "hash_b"}.get(name)

    with patch("src.graph.nodes.docstring.hash_check.get_function_hash", side_effect=_cached):
        result = function_hash_check(state)

    for fn in result["catalog"].values():
        assert not fn.is_significant


def test_function_hash_check_update_all_marks_all_significant() -> None:
    from src.graph.nodes.docstring.hash_check import function_hash_check

    state = _fn_state(update_all=True)
    # Even matching hashes: update_all forces significant
    with patch("src.graph.nodes.docstring.hash_check.get_function_hash", return_value="hash_a"):
        result = function_hash_check(state)

    for fn in result["catalog"].values():
        assert fn.is_significant


def test_function_hash_check_new_function_is_significant() -> None:
    from src.graph.nodes.docstring.hash_check import function_hash_check

    state = _fn_state()
    # No cached hash → first run → significant
    with patch("src.graph.nodes.docstring.hash_check.get_function_hash", return_value=None):
        result = function_hash_check(state)

    for fn in result["catalog"].values():
        assert fn.is_significant
