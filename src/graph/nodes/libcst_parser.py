"""Libcst_parser node — extracts function metadata from Python source files using LibCST."""

import hashlib
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
    """LibCST Visitor to extract function metadata and line numbers."""

    METADATA_DEPENDENCIES = (PositionProvider,)

    def __init__(self, filepath: Path, source_lines: list[str]):
        self.filepath = filepath
        self.source_lines = source_lines
        self.catalog: dict[str, FunctionMetadata] = {}

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        pos = self.get_metadata(PositionProvider, node)

        # Pylance fix: Ensure pos is actually a CodeRange before accessing .start
        if not isinstance(pos, CodeRange):
            return False

        start = pos.start.line
        end = pos.end.line

        prev = start - 2  # 0-indexed line immediately before this node
        if prev >= 0 and "# dp: ignore" in self.source_lines[prev]:
            return False

        src_slice = "\n".join(self.source_lines[start - 1 : end])

        # Generate a clean signature stub
        stub = node.with_changes(body=cst.IndentedBlock(body=[cst.SimpleStatementLine(body=[cst.Pass()])]))
        stub_code = cst.Module(body=[stub]).code
        signature = stub_code.split("\n")[0].strip()
        if signature.endswith(":"):
            signature = signature[:-1]

        body_hash = hashlib.sha256(normalize(src_slice).encode()).hexdigest()[:16]
        docstring = node.get_docstring()

        fn_id = make_fn_id(self.filepath, node.name.value)
        self.catalog[fn_id] = FunctionMetadata(
            name=node.name.value,
            file_path=self.filepath,
            docstring=docstring,
            start_line=start,
            end_line=end,
            signature=signature,
            body_hash=body_hash,
        )
        return False  # Do not visit nested functions

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        return True  # Visit methods inside classes


def extract_functions(source: str, filepath: Path) -> dict[str, FunctionMetadata]:
    """Pure function to extract metadata from source code using LibCST."""
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
    """Shell function to read file and call pure extraction."""
    try:
        source = filepath.read_text(encoding="utf-8")
    except OSError:
        return {}
    return extract_functions(source, filepath)


def libcst_parser(state: DocpatchState) -> ParsedFunctionsUpdate:
    """Parse every file in state.changed_files and collect function metadata."""
    full_catalog: dict[str, FunctionMetadata] = {}

    for path in state.changed_files:
        file_catalog = parse_file(path)
        logger.debug("libcst_parser: %s → %d functions", path.name, len(file_catalog))
        full_catalog.update(file_catalog)

    return {"catalog": full_catalog}
