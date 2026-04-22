import ast
import hashlib
from collections import defaultdict
from pathlib import Path

from docspatch.graph.state import DocpatchState
from docspatch.utils import cache
from docspatch.utils.ui import step


def _body_indent(lines: list[str], def_line_idx: int) -> str:
    for line in lines[def_line_idx + 1 :]:
        if line.strip():
            return line[: len(line) - len(line.lstrip())]
    return "    "


def _format_docstring(doc: str, indent: str) -> list[str]:
    text = doc.strip()
    single = f'{indent}"""{text}"""'
    if "\n" not in text and len(single) <= 79:
        return [single + "\n"]
    result = [f'{indent}"""\n']
    for line in text.split("\n"):
        result.append(f"{indent}{line.strip()}\n" if line.strip() else "\n")
    result.append(f'{indent}"""\n')
    return result


def _docstring_span(source: str, fn_name: str, fn_line_start: int) -> tuple[int, int] | None:
    """Return (start, end) 0-indexed line range of existing docstring, exclusive end."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == fn_name and node.lineno == fn_line_start:
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    doc_node = node.body[0]
                    if doc_node.end_lineno is None:
                        return None
                    return doc_node.lineno - 1, doc_node.end_lineno
    return None


def _resolve_path(filepath: str) -> Path:
    """Resolve relative paths against git repo root."""
    p = Path(filepath)
    if p.is_absolute():
        return p
    from docspatch.utils.git import get_repo, get_root
    return get_root(get_repo()) / filepath


def _write_full_file(filepath: str, content: str) -> None:
    """Write raw content to a file — used for README, CHANGELOG."""
    path = _resolve_path(filepath)
    try:
        path.write_text(content, encoding="utf-8")
    except PermissionError:
        raise RuntimeError(f"Permission denied writing {path}")
    except OSError as e:
        raise RuntimeError(f"Cannot write {path}: {e}") from e


def _apply_docstrings(filepath: str, docs: list[dict]) -> None:
    """Inject docstrings at exact AST line positions."""
    path = _resolve_path(filepath)
    try:
        source = path.read_text(encoding="utf-8")
    except PermissionError:
        raise RuntimeError(f"Permission denied reading {path}")
    except OSError as e:
        raise RuntimeError(f"Cannot read {path}: {e}") from e

    lines = source.splitlines(keepends=True)

    for doc in sorted(docs, key=lambda d: d["line_start"], reverse=True):
        generated = doc.get("generated_doc", "")
        if not generated:
            continue
        def_line_idx = doc["line_start"] - 1
        indent = _body_indent(lines, def_line_idx)
        new_lines = _format_docstring(generated, indent)
        span = _docstring_span("".join(lines), doc["name"], doc["line_start"])
        if span:
            lines[span[0] : span[1]] = new_lines
        else:
            lines[def_line_idx + 1 : def_line_idx + 1] = new_lines

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
            cache.set_file_hash(str(path), file_hash)
            cache.set_function_hashes(
                str(path), {doc["name"]: doc["body_hash"] for doc in docs}
            )
        except OSError:
            pass

    return {}
