"""writer node — safe source-file rewriter using LibCST."""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import libcst as cst

from src.schemas.graph_io import RerunDocsUpdate
from src.schemas.state import DocpatchState
from src.utils.cache import set_file_and_function_hashes
from src.utils.fs import atomic_write
from src.utils.log import get_logger

logger = get_logger(__name__)


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
    """LibCST transformer that inserts or replaces docstrings in functions and modules."""

    def __init__(self, docs: dict[str, str]) -> None:
        super().__init__()
        self.docs = docs

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.Module:
        if "__module__" not in self.docs:
            return updated_node

        doc_node = make_docstring_node(self.docs["__module__"], indent="")
        body = list(updated_node.body)
        if body and is_docstring_stmt(body[0]):
            body = [doc_node, *body[1:]]
        else:
            body = [doc_node, *body]
        return updated_node.with_changes(body=body)

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
    """Read source file, insert/replace docstrings, write atomically. Returns (success, error_msg)."""
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
    """Write accepted docstrings back to source files in parallel."""
    if state.dry_run or not state.accepted_docs:
        return {"generated_docs": {}, "token_actual": 0}

    by_file: dict[Path, dict[str, str]] = {}
    for fid, docstring in state.accepted_docs.items():
        fn = state.catalog[fid]
        by_file.setdefault(fn.file_path, {})[fn.name] = docstring

    warnings: list[str] = []
    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(apply_docstrings, fp, fd): fp for fp, fd in by_file.items()}
        for future in as_completed(futures):
            fp = futures[future]
            success, err = future.result()
            if not success and err:
                warnings.append(err)
            else:
                logger.debug("writer: wrote docstrings to %s", fp)

    return {"generated_docs": {}, "token_actual": 0, "warnings": warnings}


def cache_update(state: DocpatchState) -> RerunDocsUpdate:
    """Update file and function hashes after successful write."""
    if state.dry_run:
        return {"generated_docs": {}, "token_actual": 0}

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
