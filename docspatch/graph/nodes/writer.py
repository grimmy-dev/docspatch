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
    if not filepath:
        raise RuntimeError("Output path is empty — pass a filename (e.g. README.md).")
    p = Path(filepath)
    if p.is_absolute():
        return p
    from docspatch.utils.git import get_repo, get_root

    return get_root(get_repo()) / filepath


def _write_full_file(filepath: str, content: str) -> None:
    path = _resolve_path(filepath)
    if path.is_dir():
        raise RuntimeError(
            f"{path} is a directory. Specify a filename (e.g. README.md), not a folder."
        )
    if not path.exists():
        import questionary

        from docspatch.utils.ui import Q_STYLE, copy_to_clipboard

        from rich.console import Console as _Console

        _console = _Console()
        action = questionary.select(
            f"  {path.name} does not exist yet.",
            choices=[
                "Write to disk     — create the file",
                "Copy to clipboard — don't create the file",
                "Discard           — skip",
            ],
            instruction="(↑↓ navigate  ·  Enter select  ·  Esc cancel)",
            style=Q_STYLE,
        ).ask()
        if not action or action.startswith("Discard"):
            return
        if action.startswith("Copy"):
            ok = copy_to_clipboard(content)
            msg = (
                "Copied to clipboard."
                if ok
                else "Clipboard unavailable — paste manually."
            )
            _console.print(f"  [green]✓[/green]  {msg}")
            return
        # else: fall through to write
    try:
        path.write_text(content, encoding="utf-8")
    except PermissionError:
        raise RuntimeError(f"Permission denied writing {path}")
    except OSError as e:
        raise RuntimeError(f"Cannot write {path}: {e}") from e


def _find_function(
    tree: ast.Module,
    name: str,
    original_lineno: int,
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the function node matching name, closest to original_lineno.

    Closest-match handles line shifts caused by earlier docstring insertions in
    the same session (e.g. rerun docs whose line_start is now stale).
    """
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, _FuncNode) and node.name == name
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda n: abs(n.lineno - original_lineno))


def _apply_docstrings(filepath: str, docs: list[dict]) -> None:
    """Inject docstrings at body[0].lineno — correct for multi-line signatures."""
    path = _resolve_path(filepath)
    try:
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    except PermissionError:
        raise RuntimeError(f"Permission denied reading {path}")
    except OSError as e:
        raise RuntimeError(f"Cannot read {path}: {e}") from e

    modified = False
    for doc in sorted(docs, key=lambda d: d["line_start"], reverse=True):
        generated = doc.get("generated_doc", "")
        if not generated:
            continue

        # Re-parse current lines each iteration — positions shift after each edit
        try:
            tree = ast.parse("".join(lines))
        except SyntaxError:
            continue

        target = _find_function(tree, doc["name"], doc["line_start"])
        if not target or not target.body:
            continue

        first_stmt = target.body[0]
        body_idx = first_stmt.lineno - 1  # 0-based; body starts after closing ):
        indent = " " * first_stmt.col_offset
        new_lines = _format_docstring(generated, indent)

        # Replace existing docstring; otherwise insert before first statement
        if (
            isinstance(first_stmt, ast.Expr)
            and isinstance(first_stmt.value, ast.Constant)
            and isinstance(first_stmt.value.value, str)
            and first_stmt.end_lineno is not None
        ):
            lines[body_idx : first_stmt.end_lineno] = new_lines
        else:
            lines[body_idx:body_idx] = new_lines
        modified = True

    if not modified:
        return

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
        # Full-file write for README/CHANGELOG (no line_start); otherwise inject
        if docs[0].get("line_start") is None:
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
