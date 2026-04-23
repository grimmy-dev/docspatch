import ast
import hashlib
from collections import defaultdict
from pathlib import Path

from docspatch.graph.state import DocpatchState
from docspatch.utils.cache import set_file_and_function_hashes
from docspatch.utils.ui import step

_FuncNode = (ast.FunctionDef, ast.AsyncFunctionDef)


def _format_docstring(doc: str, indent: str) -> list[str]:
    text = doc.strip()
    single = f'{indent}"""{text}"""'
    if "\n" not in text and len(single) <= 79:
        return [single + "\n"]
    result = [f'{indent}"""\n']
    lines = text.split("\n")
    non_empty = [ln for ln in lines if ln.strip()]
    min_ind = min((len(ln) - len(ln.lstrip()) for ln in non_empty), default=0)
    for ln in lines:
        if ln.strip():
            result.append(f"{indent}{ln[min_ind:]}\n")
        else:
            result.append("\n")
    result.append(f'{indent}"""\n')
    return result


def _resolve_path(filepath: str) -> Path:
    p = Path(filepath)
    if p.is_absolute():
        return p
    from docspatch.utils.git import get_repo, get_root

    return get_root(get_repo()) / filepath


def _write_full_file(filepath: str, content: str) -> None:
    path = _resolve_path(filepath)
    try:
        path.write_text(content, encoding="utf-8")
    except PermissionError:
        raise RuntimeError(f"Permission denied writing {path}")
    except OSError as e:
        raise RuntimeError(f"Cannot write {path}: {e}") from e


def _apply_docstrings(filepath: str, docs: list[dict]) -> None:
    """Inject docstrings using AST body[0].lineno — handles multi-line signatures."""
    path = _resolve_path(filepath)
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except PermissionError:
        raise RuntimeError(f"Permission denied reading {path}")
    except OSError as e:
        raise RuntimeError(f"Cannot read {path}: {e}") from e

    for doc in sorted(docs, key=lambda d: d["line_start"], reverse=True):
        generated = doc.get("generated_doc", "")
        if not generated:
            continue

        # Re-parse current lines each iteration (positions shift after edits)
        try:
            tree = ast.parse("".join(lines))
        except SyntaxError:
            continue

        target: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        for node in ast.walk(tree):
            if (
                isinstance(node, _FuncNode)
                and node.name == doc["name"]
                and node.lineno == doc["line_start"]
            ):
                target = node  # type: ignore[assignment]
                break

        if not target or not target.body:
            continue

        first_stmt = target.body[0]
        body_idx = first_stmt.lineno - 1  # 0-indexed line where body starts
        indent = " " * first_stmt.col_offset
        new_lines = _format_docstring(generated, indent)

        # Replace existing docstring vs fresh insert
        if (
            isinstance(first_stmt, ast.Expr)
            and isinstance(first_stmt.value, ast.Constant)
            and isinstance(first_stmt.value.value, str)
            and first_stmt.end_lineno is not None
        ):
            lines[body_idx : first_stmt.end_lineno] = new_lines
        else:
            lines[body_idx:body_idx] = new_lines

    try:
        path.write_text("".join(lines), encoding="utf-8")
    except PermissionError:
        raise RuntimeError(f"Permission denied writing {path}")
    except OSError as e:
        raise RuntimeError(f"Cannot write {path}: {e}") from e


def writer(state: DocpatchState) -> dict:
    by_file: dict[str, list[dict]] = defaultdict(list)
    for doc in state["accepted_docs"]:
        by_file[doc["file"]].append(doc)

    for filepath, docs in by_file.items():
        # Full-file write: README, CHANGELOG (no line_start)
        if "line_start" not in docs[0]:
            _write_full_file(filepath, docs[0].get("generated_doc", ""))
        else:
            _apply_docstrings(filepath, docs)

    if by_file:
        step("Writing", f"{len(by_file)} file(s) updated")
    return {}


def cache_update(state: DocpatchState) -> dict:
    by_file: dict[str, list[dict]] = defaultdict(list)
    for doc in state["accepted_docs"]:
        if "line_start" not in doc:
            continue  # README/CLG don't need function-level caching
        by_file[doc["file"]].append(doc)

    for filepath, docs in by_file.items():
        try:
            path = _resolve_path(filepath)
            file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            set_file_and_function_hashes(
                str(path),
                file_hash,
                {doc["name"]: doc["body_hash"] for doc in docs},
            )
        except OSError:
            pass

    return {}
