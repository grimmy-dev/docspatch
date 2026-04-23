import ast
import hashlib

from docspatch.graph.state import DocpatchState
from docspatch.utils.differ import normalize
from docspatch.utils.ui import step

_FuncNode = ast.FunctionDef | ast.AsyncFunctionDef


def _iter_functions(tree: ast.Module):
    """Yield top-level functions and class methods. Skip nested functions."""
    for node in tree.body:
        if isinstance(node, _FuncNode):
            yield node
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, _FuncNode):
                    yield child


def _existing_doc(node: _FuncNode) -> str:
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        return node.body[0].value.value
    return ""


def _parse_file(filepath: str) -> list[dict]:
    try:
        with open(filepath, encoding="utf-8") as f:
            source = f.read()
    except OSError:
        return []

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    lines = source.splitlines()
    functions = []

    for node in _iter_functions(tree):
        body_source = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"

        functions.append(
            {
                "name": node.name,
                "file": filepath,
                "line_start": node.lineno,
                "line_end": node.end_lineno,
                "signature": f"{prefix} {node.name}({ast.unparse(node.args)})",
                "body": body_source,
                "existing_doc": _existing_doc(node),
                "body_hash": hashlib.sha256(
                    normalize(body_source).encode()
                ).hexdigest(),
                "is_significant": True,  # function_hash_check updates this
            }
        )

    return functions


def ast_parser(state: DocpatchState) -> dict:
    """Extract all functions from changed files."""
    parsed: list[dict] = []
    for filepath in state["changed_files"]:
        parsed.extend(_parse_file(filepath))
    step("Parsing", f"{len(parsed)} functions")
    return {"parsed_functions": parsed}
