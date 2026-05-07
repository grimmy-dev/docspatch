"""Tests for writer.transform_source — pure LibCST transformation."""

import pytest

from src.graph.nodes.docstring.writer import transform_source


def test_inserts_docstring_on_undocumented_function() -> None:
    src = "def greet():\n    return 'hi'\n"
    result = transform_source(src, {"greet": "Say hi."})
    assert '"""Say hi."""' in result
    assert "return 'hi'" in result


def test_replaces_existing_docstring() -> None:
    src = 'def greet():\n    """Old doc."""\n    return "hi"\n'
    result = transform_source(src, {"greet": "New doc."})
    assert "New doc." in result
    assert "Old doc." not in result


def test_skips_function_not_in_docs() -> None:
    src = "def a():\n    pass\n\ndef b():\n    pass\n"
    result = transform_source(src, {"a": "Doc for a."})
    assert "Doc for a." in result
    # b untouched — no docstring inserted
    assert result.count('"""') == 2  # one open + one close for a only


def test_multiple_functions_in_one_pass() -> None:
    src = "def f():\n    pass\n\ndef g():\n    pass\n"
    result = transform_source(src, {"f": "F doc.", "g": "G doc."})
    assert "F doc." in result
    assert "G doc." in result


def test_empty_docs_returns_source_unchanged() -> None:
    src = "def f():\n    pass\n"
    assert transform_source(src, {}) == src


def test_invalid_python_raises() -> None:
    with pytest.raises(Exception):  # noqa: B017
        transform_source("def broken(", {"broken": "doc"})
