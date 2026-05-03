"""libcst_parser node — extracts function and module-level metadata using LibCST."""

import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import libcst as cst
from libcst.metadata import CodeRange, MetadataWrapper, PositionProvider

from src.schemas.function import FunctionMetadata, make_fn_id
from src.schemas.graph_io import ParsedFunctionsUpdate
from src.schemas.state import DocpatchState
from src.utils.differ import normalize
from src.utils.log import get_logger

logger = get_logger(__name__)


class FunctionExtractor(cst.CSTVisitor):
    """LibCST Visitor to extract function and module-level metadata."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, filepath: Path, source_lines: list[str]):
        self.filepath = filepath
        self.source_lines = source_lines
        self.catalog: dict[str, FunctionMetadata] = {}

    def _is_docstring_stmt(self, node: cst.CSTNode) -> bool:
        return (
            isinstance(node, cst.SimpleStatementLine)
            and len(node.body) == 1
            and isinstance(node.body[0], cst.Expr)
            and isinstance(node.body[0].value, (cst.SimpleString, cst.ConcatenatedString, cst.FormattedString))
        )

    def visit_Module(self, node: cst.Module) -> bool | None:
        has_docstring = node.body and self._is_docstring_stmt(node.body[0])
        fn_id = make_fn_id(self.filepath, "__module__")

        if has_docstring:
            docstring_text = node.get_docstring()
            pos = self.get_metadata(PositionProvider, node.body[0])
            end_line = pos.end.line if isinstance(pos, CodeRange) else 1
            body_hash = hashlib.sha256((docstring_text or "").encode()).hexdigest()[:16]
            self.catalog[fn_id] = FunctionMetadata(
                kind="module",
                name="__module__",
                file_path=self.filepath,
                docstring=docstring_text,
                start_line=1,
                end_line=end_line,
                signature=f"# {self.filepath.name}",
                body_hash=body_hash,
            )
        else:
            self.catalog[fn_id] = FunctionMetadata(
                kind="module",
                name="__module__",
                file_path=self.filepath,
                docstring=None,
                start_line=1,
                end_line=1,
                signature=f"# {self.filepath.name}",
                body_hash=hashlib.sha256(b"").hexdigest()[:16],
            )
        return None  # continue visiting children

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        pos = self.get_metadata(PositionProvider, node)
        if not isinstance(pos, CodeRange):
            return False

        start = pos.start.line
        end = pos.end.line

        prev = start - 2
        if prev >= 0 and "# dp: ignore" in self.source_lines[prev]:
            return False

        src_slice = "\n".join(self.source_lines[start - 1 : end])

        stub = node.with_changes(body=cst.IndentedBlock(body=[cst.SimpleStatementLine(body=[cst.Pass()])]))
        stub_code = cst.Module(body=[stub]).code
        signature = stub_code.split("\n")[0].strip()
        if signature.endswith(":"):
            signature = signature[:-1]

        body_hash = hashlib.sha256(normalize(src_slice).encode()).hexdigest()[:16]
        docstring = node.get_docstring()

        fn_id = make_fn_id(self.filepath, node.name.value)
        self.catalog[fn_id] = FunctionMetadata(
            kind="function",
            name=node.name.value,
            file_path=self.filepath,
            docstring=docstring,
            start_line=start,
            end_line=end,
            signature=signature,
            body_hash=body_hash,
        )
        return False  # do not visit nested functions

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        return True  # visit methods inside classes


def extract_functions(source: str, filepath: Path) -> dict[str, FunctionMetadata]:
    """Extract function and module metadata from Python source using LibCST."""
    try:
        module = cst.parse_module(source)
        wrapper = MetadataWrapper(module)
    except cst.ParserSyntaxError as exc:
        logger.warning("SyntaxError parsing %s: %s", filepath, exc)
        return {}

    source_lines = source.splitlines()
    extractor = FunctionExtractor(filepath, source_lines)
    wrapper.visit(extractor)
    return extractor.catalog


def parse_file(filepath: Path) -> dict[str, FunctionMetadata]:
    """Read file and extract all metadata."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except OSError:
        return {}
    return extract_functions(source, filepath)


def libcst_parser(state: DocpatchState) -> ParsedFunctionsUpdate:
    """Parse every file in state.changed_files in parallel and collect metadata."""
    full_catalog: dict[str, FunctionMetadata] = {}

    with ThreadPoolExecutor() as executor:
        futures = {executor.submit(parse_file, path): path for path in state.changed_files}
        for future in as_completed(futures):
            path = futures[future]
            file_catalog = future.result()
            logger.debug("libcst_parser: %s → %d entries", path.name, len(file_catalog))
            full_catalog.update(file_catalog)

    return {"catalog": full_catalog}
