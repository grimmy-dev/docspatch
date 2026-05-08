"""Tests for filter_significant — pure catalog filter."""

from pathlib import Path

from src.graph.nodes.docstring.significance import filter_significant
from src.schemas.function import FunctionMetadata


def _fn(name: str, *, significant: bool) -> FunctionMetadata:
    return FunctionMetadata(
        name=name,
        file_path=Path("src/foo.py"),
        start_line=1,
        end_line=5,
        signature=f"def {name}()",
        body_hash="abc123",
        is_significant=significant,
    )


def test_keeps_only_significant_entries() -> None:
    catalog = {
        "src/foo.py::alpha": _fn("alpha", significant=True),
        "src/foo.py::beta": _fn("beta", significant=False),
        "src/foo.py::gamma": _fn("gamma", significant=True),
    }
    ids, pruned = filter_significant(catalog)
    assert set(ids) == {"src/foo.py::alpha", "src/foo.py::gamma"}
    assert set(pruned.keys()) == {"src/foo.py::alpha", "src/foo.py::gamma"}


def test_returns_empty_for_empty_catalog() -> None:
    ids, pruned = filter_significant({})
    assert ids == []
    assert pruned == {}


def test_all_insignificant_returns_empty() -> None:
    catalog = {
        "src/foo.py::alpha": _fn("alpha", significant=False),
        "src/foo.py::beta": _fn("beta", significant=False),
    }
    ids, pruned = filter_significant(catalog)
    assert ids == []
    assert pruned == {}


def test_pruned_catalog_keys_match_ids() -> None:
    catalog = {
        "src/foo.py::alpha": _fn("alpha", significant=True),
        "src/foo.py::beta": _fn("beta", significant=False),
    }
    ids, pruned = filter_significant(catalog)
    assert set(ids) == set(pruned.keys())


def test_pruned_catalog_values_are_original_metadata() -> None:
    fn = _fn("alpha", significant=True)
    catalog = {"src/foo.py::alpha": fn}
    _, pruned = filter_significant(catalog)
    assert pruned["src/foo.py::alpha"] is fn


def _trivial_fn(name: str, *, docstring: str | None, significant: bool) -> FunctionMetadata:
    return FunctionMetadata(
        name=name,
        file_path=Path("src/foo.py"),
        start_line=1,
        end_line=2,  # end - start == 1: trivial
        signature=f"def {name}()",
        body_hash="abc123",
        is_significant=significant,
        docstring=docstring,
    )


def test_trivial_function_with_docstring_excluded() -> None:
    fn = _trivial_fn("tiny", docstring="Already documented.", significant=True)
    catalog = {"src/foo.py::tiny": fn}
    ids, _ = filter_significant(catalog)
    assert ids == []


def test_trivial_function_without_docstring_included() -> None:
    fn = _trivial_fn("tiny", docstring=None, significant=True)
    catalog = {"src/foo.py::tiny": fn}
    ids, _ = filter_significant(catalog)
    assert "src/foo.py::tiny" in ids


def test_non_trivial_function_with_docstring_included() -> None:
    fn = FunctionMetadata(
        name="big",
        file_path=Path("src/foo.py"),
        start_line=1,
        end_line=10,  # end - start == 9: not trivial
        signature="def big()",
        body_hash="abc123",
        is_significant=True,
        docstring="Existing doc.",
    )
    catalog = {"src/foo.py::big": fn}
    ids, _ = filter_significant(catalog)
    assert "src/foo.py::big" in ids
