"""AST-based usage example extraction for README context enrichment.

Core layer — no LLM, no network. Reads test/main files to extract real call patterns."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TypedDict

__all__ = ["UsageExample", "extract_usage_examples"]

_SKIP_NAMES = frozenset(
    {
        "assert",
        "mock",
        "patch",
        "MagicMock",
        "setUp",
        "tearDown",
        "pytest",
        "fixture",
        "mark",
        "raises",
        "warns",
    }
)


class UsageExample(TypedDict):
    """A single usage call extracted from tests or main entry points."""

    source: str  # "test" | "main"
    fn_name: str  # function/class being demonstrated
    call: str  # unparsed call, truncated to 80 chars
    context: str | None  # assert/check line that follows, if any


def _called_name(node: ast.Call) -> str | None:
    """Return the top-level callable name from a Call node, or None if it should be skipped."""
    if isinstance(node.func, ast.Name):
        name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        name = node.func.attr
    else:
        return None
    parts = name.split(".")
    if any(part in _SKIP_NAMES for part in parts) or name in _SKIP_NAMES:
        return None
    return name


def _make_example(source: str, name: str, call_node: ast.Call, next_stmt: ast.stmt | None) -> UsageExample:
    """Build a UsageExample from an AST call node and optional following statement."""
    call_str = ast.unparse(call_node)[:80]
    context: str | None = None
    if isinstance(next_stmt, ast.Assert):
        context = ast.unparse(next_stmt)[:60]
    return UsageExample(source=source, fn_name=name, call=call_str, context=context)


def _extract_from_test_file(path: Path) -> list[UsageExample]:
    """Parse a test file and return one UsageExample per unique called function."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as _:
        return []

    examples: list[UsageExample] = []
    seen: set[str] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("test_"):
            continue
        stmts = node.body
        for i, stmt in enumerate(stmts):
            if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
                continue
            name = _called_name(stmt.value)
            if name is None or name in seen:
                continue
            next_stmt = stmts[i + 1] if i + 1 < len(stmts) else None
            examples.append(_make_example("test", name, stmt.value, next_stmt))
            seen.add(name)

    return examples


def _extract_from_main_file(path: Path) -> list[UsageExample]:
    """Parse a __main__ file and return UsageExamples from the if __name__ == '__main__' block."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as _:
        return []

    examples: list[UsageExample] = []
    seen: set[str] = set()

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.If):
            continue
        test = node.test
        is_main_guard = (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq)
            and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and test.comparators[0].value == "__main__"
        )
        if not is_main_guard:
            continue
        stmts = node.body
        for i, stmt in enumerate(stmts):
            if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
                continue
            name = _called_name(stmt.value)
            if name is None or name in seen:
                continue
            next_stmt = stmts[i + 1] if i + 1 < len(stmts) else None
            examples.append(_make_example("main", name, stmt.value, next_stmt))
            seen.add(name)

    return examples


def _collect_test_examples(root: Path) -> list[UsageExample]:
    """Gather UsageExamples from all test_*.py files under tests/ or test/."""
    examples: list[UsageExample] = []
    for subdir in ("tests", "test"):
        test_dir = root / subdir
        if test_dir.exists():
            for p in sorted(test_dir.rglob("test_*.py")):
                examples.extend(_extract_from_test_file(p))
    for p in sorted(root.glob("test_*.py")):
        examples.extend(_extract_from_test_file(p))
    return examples


def _collect_main_examples(root: Path) -> list[UsageExample]:
    """Gather UsageExamples from __main__.py and files containing a __main__ guard."""
    examples: list[UsageExample] = []
    main_file = root / "__main__.py"
    if main_file.exists():
        examples.extend(_extract_from_main_file(main_file))
    for p in root.rglob("*.py"):
        if p == main_file:
            continue
        try:
            if "__main__" in p.read_text(encoding="utf-8"):
                examples.extend(_extract_from_main_file(p))
        except OSError:
            continue
    return examples


def extract_usage_examples(root: Path, *, max_examples: int = 20) -> list[UsageExample]:
    """Return up to max_examples usage calls extracted from tests and __main__ files.

    Test examples take priority over main examples. Deduplicates by fn_name globally."""
    test_examples = _collect_test_examples(root)
    main_examples = _collect_main_examples(root)

    seen: set[str] = set()
    combined: list[UsageExample] = []
    for ex in test_examples + main_examples:
        if ex["fn_name"] not in seen:
            combined.append(ex)
            seen.add(ex["fn_name"])

    return combined[:max_examples]
