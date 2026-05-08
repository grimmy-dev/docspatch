"""ast_compress — pure core utility to compress Python source to a skeleton.

Strips function bodies and inline comments; retains class names, function
signatures, type hints, and docstrings. Output is valid, parseable Python.
"""

import ast
from pathlib import Path

__all__ = ["compress_file", "compress_source"]

_DOCSTRING_VALUE_TYPES = (str,)


def _is_docstring(node: ast.stmt) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, _DOCSTRING_VALUE_TYPES)


def _ellipsis_stmt() -> ast.Expr:
    return ast.Expr(value=ast.Constant(value=...))


class _BodyStripper(ast.NodeTransformer):
    """Replace function bodies with '...', keeping signatures and docstrings."""

    def _strip(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.FunctionDef | ast.AsyncFunctionDef:
        node = self.generic_visit(node)  # type: ignore[assignment]

        new_body: list[ast.stmt] = []
        if node.body and _is_docstring(node.body[0]):
            new_body.append(node.body[0])

        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                new_body.append(stmt)

        node.body = new_body or [_ellipsis_stmt()]
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        return self._strip(node)  # type: ignore[return-value]

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AsyncFunctionDef:
        return self._strip(node)  # type: ignore[return-value]


def compress_source(source: str) -> str:
    """Return a compressed skeleton of Python source.

    Strips all function bodies and inline comments. Retains: class
    names, function signatures, type hints, and docstrings. Output is
    valid Python.
    """
    tree = ast.parse(source)
    stripped = _BodyStripper().visit(tree)
    ast.fix_missing_locations(stripped)
    return ast.unparse(stripped)


def compress_file(path: Path) -> str | None:
    """Read a Python file and return its compressed skeleton.

    Returns None on read or parse failure.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        return compress_source(source)
    except SyntaxError:
        return None
