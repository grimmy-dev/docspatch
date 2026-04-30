"""writer node — safe source-file rewriter using LibCST."""

import os
from pathlib import Path

import libcst as cst

from src.schemas.graph_io import RerunDocsUpdate
from src.schemas.state import DocpatchState
from src.utils.cache import set_file_and_function_hashes
from src.utils.log import get_logger

logger = get_logger(__name__)


def atomic_write(path: Path, content: str) -> None:
    """Write content to path via a temp file; cleans up on any failure."""
    tmp = Path(str(path) + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


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


def make_docstring_node(text: str, indent: str = "    ") -> cst.SimpleStatementLine:
    """Build a CST node for a triple-quoted docstring with proper indentation."""
    escaped = text.replace('"""', '\\"\\"\\"')
    lines = escaped.splitlines()
    if len(lines) > 1:
        escaped = lines[0] + "\n" + "\n".join(f"{indent}{line}" if line else "" for line in lines[1:])

    return cst.SimpleStatementLine(
        body=[cst.Expr(value=cst.SimpleString(f'"""{escaped}"""'))],
        leading_lines=[],
    )


def transform_source(source: str, docs: dict[str, str]) -> str:
    """Pure function to apply docstrings to source code."""
    tree = cst.parse_module(source)
    updated = tree.visit(DocstringInserter(docs))
    return updated.code


class DocstringInserter(cst.CSTTransformer):
    """LibCST transformer that inserts or replaces docstrings in function defs."""

    def __init__(self, docs: dict[str, str]) -> None:
        super().__init__()
        self.docs = docs

    def leave_FunctionDef(
        self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef
    ) -> cst.BaseStatement | cst.FlattenSentinel[cst.BaseStatement] | cst.RemovalSentinel:
        name = updated_node.name.value
        if name not in self.docs:
            return updated_node

        indent = "    "
        if isinstance(updated_node.body, cst.IndentedBlock) and updated_node.body.indent is not None:
            indent = updated_node.body.indent

        doc_node = make_docstring_node(self.docs[name], indent=indent)
        existing = list(updated_node.body.body)
        body_stmts = [doc_node, *existing[1:]] if existing and is_docstring_stmt(existing[0]) else [doc_node, *existing]
        return updated_node.with_changes(body=updated_node.body.with_changes(body=body_stmts))


def apply_docstrings(filepath: Path, docs: dict[str, str]) -> tuple[bool, str | None]:
    """Shell function to read, transform, and write file. Returns (success, error_msg)."""
    if not docs:
        return True, None
    try:
        source = filepath.read_text(encoding="utf-8")
        new_source = transform_source(source, docs)
        if new_source != source:
            atomic_write(filepath, new_source)
        return True, None
    except cst.ParserSyntaxError as exc:
        logger.warning("Syntax error in %s, skipping docstring insertion: %s", filepath, exc)
        return False, f"Syntax error in {filepath.name}, skipped writing docstrings."
    except OSError as exc:
        logger.error("Failed to update %s: %s", filepath, exc)
        return False, f"Failed to update {filepath.name}: {exc}"


def writer(state: DocpatchState) -> RerunDocsUpdate:
    """Write accepted docstrings back to source files."""
    if state.dry_run or not state.accepted_docs:
        return {"generated_docs": {}, "token_actual": 0}

    by_file: dict[Path, dict[str, str]] = {}
    for fid, docstring in state.accepted_docs.items():
        fn = state.catalog[fid]
        by_file.setdefault(fn.file_path, {})[fn.name] = docstring

    warnings = []
    for filepath, file_docs in by_file.items():
        success, err = apply_docstrings(filepath, file_docs)
        if not success and err:
            warnings.append(err)
        else:
            logger.debug("writer: wrote %d docstrings to %s", len(file_docs), filepath)

    return {"generated_docs": {}, "token_actual": 0, "warnings": warnings}


def cache_update(state: DocpatchState) -> RerunDocsUpdate:
    """Update file and function hashes after successful write."""
    if state.dry_run:
        return {"generated_docs": {}, "token_actual": 0}

    import hashlib

    by_file: dict[Path, list[str]] = {}
    for fid in state.accepted_docs.keys():
        fn = state.catalog[fid]
        by_file.setdefault(fn.file_path, []).append(fid)

    for filepath, fids in by_file.items():
        try:
            file_hash = hashlib.sha256(filepath.read_bytes()).hexdigest()
            hashes = {state.catalog[fid].name: state.catalog[fid].body_hash for fid in fids}
            set_file_and_function_hashes(filepath, file_hash, hashes)
        except OSError as exc:
            logger.warning("cache_update failed for %s: %s", filepath, exc)

    return {"generated_docs": {}, "token_actual": 0}
