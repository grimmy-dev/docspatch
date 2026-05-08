"""README signals — test coverage extraction."""

import ast
from pathlib import Path

__all__ = ["get_test_coverage_summary"]

_TEST_NAMES_PER_MODULE = 6


def get_test_coverage_summary(root: Path) -> str:
    """Return test function names grouped by module as plain-english behaviour signals.

    Caps at _TEST_NAMES_PER_MODULE names per module. Uses rglob to find nested test dirs.
    Empty string when no tests found."""
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return ""
    modules: dict[str, list[str]] = {}
    for test_file in sorted(tests_dir.rglob("test_*.py")):
        try:
            tree = ast.parse(test_file.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as _:
            continue
        names = [
            node.name.removeprefix("test_").replace("_", " ")
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        ]
        if names:
            module_name = test_file.stem.removeprefix("test_").replace("_", " ").title()
            modules[module_name] = names[:_TEST_NAMES_PER_MODULE]
    if not modules:
        return ""
    parts = "; ".join(f"{mod}: {', '.join(names)}" for mod, names in modules.items())
    return f"Tests — {parts}"
