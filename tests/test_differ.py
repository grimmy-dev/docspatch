"""Tests for differ.normalize and is_significant."""

import pytest

from src.utils.differ import is_significant, normalize


def test_normalize_strips_full_line_comments() -> None:
    src = "def f():\n    # this is a comment\n    return 1"
    assert "comment" not in normalize(src)


def test_normalize_does_not_strip_inline_url() -> None:
    src = "x = 'https://example.com'  # not a full-line comment"
    result = normalize(src)
    assert "example.com" in result


def test_normalize_strips_triple_double_docstring() -> None:
    src = '"""Module doc."""\ndef f(): pass'
    assert "Module doc" not in normalize(src)


def test_normalize_strips_triple_single_docstring() -> None:
    src = "'''doc'''\ndef f(): pass"
    assert "doc" not in normalize(src)


def test_normalize_collapses_whitespace() -> None:
    result = normalize("x  =   1\n\n\ny  =  2")
    assert "  " not in result


@pytest.mark.parametrize(
    "old, new, expected",
    [
        # logic change → significant
        ("return 1", "return 2", True),
        ("x = a + b", "x = a - b", True),
        # full-line comment-only change → not significant (inline comments kept by design)
        ("# old comment\nreturn 1", "# new comment\nreturn 1", False),
        # docstring-only change → not significant
        ('"""old doc"""\nreturn 1', '"""new doc"""\nreturn 1', False),
        # whitespace-only change → not significant
        ("return  1", "return 1", False),
        # identical → not significant
        ("return x", "return x", False),
    ],
)
def test_is_significant(old: str, new: str, expected: bool) -> None:
    assert is_significant(old, new) is expected
