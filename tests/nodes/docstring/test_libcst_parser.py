"""Tests for extract_functions — pure function, no I/O."""

from pathlib import Path

from src.graph.nodes.docstring.libcst_parser import extract_functions

FAKE_PATH = Path("src/module.py")

SOURCE = '''\
def greet(name: str) -> str:
    """Say hello.

    Args:
        name: Person to greet.

    Returns:
        Greeting string.
    """
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    return a + b


class MyClass:
    def method(self) -> None:
        """A method."""
        pass
'''


def test_extracts_top_level_functions() -> None:
    catalog = extract_functions(SOURCE, FAKE_PATH)
    names = {fn.name for fn in catalog.values()}
    assert "greet" in names
    assert "add" in names


def test_extracts_class_methods() -> None:
    catalog = extract_functions(SOURCE, FAKE_PATH)
    names = {fn.name for fn in catalog.values()}
    assert "method" in names


def test_docstring_captured() -> None:
    catalog = extract_functions(SOURCE, FAKE_PATH)
    fn = next(fn for fn in catalog.values() if fn.name == "greet")
    assert fn.docstring is not None
    assert "Say hello" in fn.docstring


def test_no_docstring_is_none() -> None:
    catalog = extract_functions(SOURCE, FAKE_PATH)
    fn = next(fn for fn in catalog.values() if fn.name == "add")
    assert fn.docstring is None


def test_body_hash_is_stable() -> None:
    c1 = extract_functions(SOURCE, FAKE_PATH)
    c2 = extract_functions(SOURCE, FAKE_PATH)
    for fn_id in c1:
        assert c1[fn_id].body_hash == c2[fn_id].body_hash


def test_dp_ignore_skips_function() -> None:
    source = """\
# dp: ignore
def hidden() -> None:
    pass


def visible() -> None:
    pass
"""
    catalog = extract_functions(source, FAKE_PATH)
    names = {fn.name for fn in catalog.values()}
    assert "visible" in names
    assert "hidden" not in names


def test_syntax_error_returns_empty() -> None:
    catalog = extract_functions("def foo(: broken", FAKE_PATH)
    assert catalog == {}


def test_file_path_set_on_all_functions() -> None:
    catalog = extract_functions(SOURCE, FAKE_PATH)
    for fn in catalog.values():
        assert fn.file_path == FAKE_PATH
