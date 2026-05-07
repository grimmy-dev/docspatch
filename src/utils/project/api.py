"""AST-based public API scanning for Python project directories.

Shell layer — reads Python files from disk to extract public symbol names and docstrings.
"""

import ast
from pathlib import Path

from src.utils.project.format import NOISE_DIRS

__all__ = ["scan_public_api"]

_NamedNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _docstring_summary(node: _NamedNode) -> str | None:
    """Return the first line of a node's docstring, or None if absent."""
    doc = ast.get_docstring(node)
    if not doc:
        return None
    return doc.splitlines()[0].strip()


def _fmt_symbol(name: str, node: _NamedNode) -> str:
    """Format a symbol as 'name — summary' or just 'name' when no summary exists."""
    summary = _docstring_summary(node)
    return f"{name} — {summary}" if summary else name


def _extract_public_symbols(path: Path) -> list[str]:
    """Return public symbols from a Python file as 'name — summary' strings.

    Respects __all__ if defined. Otherwise includes top-level functions, classes, and
    constants not starting with an underscore."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as _:
        return []

    top_level: dict[str, _NamedNode] = {
        node.name: node for node in ast.iter_child_nodes(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        names = [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
                        return [_fmt_symbol(n, top_level[n]) if n in top_level else n for n in names]

    return [_fmt_symbol(name, node) for name, node in top_level.items() if not name.startswith("_")]


def scan_public_api(target: Path) -> dict[str, list[str]]:
    """Extract exported public symbols from Python files under target.

    Files in NOISE_DIRS or starting with _ (except __init__.py) are excluded."""
    result: dict[str, list[str]] = {}
    for py_file in sorted(target.rglob("*.py")):
        if any(part in NOISE_DIRS for part in py_file.parts):
            continue
        if py_file.stem.startswith("_") and py_file.stem != "__init__":
            continue
        symbols = _extract_public_symbols(py_file)
        if symbols:
            result[str(py_file.relative_to(target))] = symbols
    return result
