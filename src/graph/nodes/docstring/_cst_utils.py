"""Shared LibCST predicates for the docstring node subpackage."""

import libcst as cst

__all__ = ["is_docstring_stmt"]


def is_docstring_stmt(node: cst.CSTNode) -> bool:
    """Return True when node is a bare string expression (docstring)."""
    return (
        isinstance(node, cst.SimpleStatementLine)
        and len(node.body) == 1
        and isinstance(node.body[0], cst.Expr)
        and isinstance(
            node.body[0].value,
            (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString),
        )
    )
