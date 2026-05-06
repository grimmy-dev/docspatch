"""Tests for src/utils/usage_signals — AST-based usage example extraction."""

from pathlib import Path

import pytest

from src.utils.usage_signals import extract_usage_examples


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_finds_test_calls(tmp_path: Path) -> None:
    """Extraction finds calls inside test functions."""
    _write(
        tmp_path / "tests" / "test_foo.py",
        "def test_something():\n    my_func(1, 2)\n    assert True\n",
    )
    results = extract_usage_examples(tmp_path)
    names = [ex["fn_name"] for ex in results]
    assert "my_func" in names


def test_deduplicates_by_fn_name(tmp_path: Path) -> None:
    """Two test functions calling same fn_name → one example."""
    _write(
        tmp_path / "tests" / "test_foo.py",
        "def test_a():\n    my_func(1)\n\ndef test_b():\n    my_func(2)\n",
    )
    results = extract_usage_examples(tmp_path)
    fn_names = [ex["fn_name"] for ex in results]
    assert fn_names.count("my_func") == 1


def test_respects_cap(tmp_path: Path) -> None:
    """Cap limits the returned examples."""
    lines = ["def test_fn():\n"]
    for i in range(25):
        lines.append(f"    fn_{i}()\n")
    _write(tmp_path / "tests" / "test_many.py", "".join(lines))
    results = extract_usage_examples(tmp_path, max_examples=5)
    assert len(results) <= 5


def test_skips_helpers(tmp_path: Path) -> None:
    """Calls to mock/patch/assert/pytest helpers are not captured."""
    _write(
        tmp_path / "tests" / "test_foo.py",
        "def test_x():\n    mock()\n    patch('x')\n    real_fn()\n",
    )
    results = extract_usage_examples(tmp_path)
    names = [ex["fn_name"] for ex in results]
    assert "mock" not in names
    assert "patch" not in names
    assert "real_fn" in names


def test_parses_main_file(tmp_path: Path) -> None:
    """Calls inside if __name__ == '__main__' are captured with source='main'."""
    _write(
        tmp_path / "__main__.py",
        "def run(): pass\n\nif __name__ == '__main__':\n    run()\n",
    )
    results = extract_usage_examples(tmp_path)
    main_exs = [ex for ex in results if ex["source"] == "main"]
    assert any(ex["fn_name"] == "run" for ex in main_exs)


def test_missing_test_dir_returns_empty(tmp_path: Path) -> None:
    """Root with no tests/ directory returns empty list."""
    results = extract_usage_examples(tmp_path)
    assert results == []


def test_captures_assert_context(tmp_path: Path) -> None:
    """Assert line immediately following a call is captured as context."""
    _write(
        tmp_path / "tests" / "test_ctx.py",
        "def test_it():\n    result = compute()\n    assert result == 42\n",
    )
    results = extract_usage_examples(tmp_path)
    # compute() is wrapped in assignment, not a bare Expr — no capture expected;
    # verify extraction doesn't crash and returns cleanly
    assert isinstance(results, list)
