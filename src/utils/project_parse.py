"""I/O functions for parsing project metadata from disk.

Shell layer — reads from the filesystem only, delegates pure logic to project_format.
"""

import ast
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.readme_io import ProjectContext
from src.utils.log import get_logger
from src.utils.project_format import MAX_README_CHARS, NOISE_DIRS, compact_readme

__all__ = [
    "build_dir_tree",
    "find_init_docstring",
    "load_existing_readme",
    "parse_pyproject",
    "scan_public_api",
]

logger = get_logger(__name__)

_NamedNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


class _PyprojectProject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    version: str | None = None
    description: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    scripts: dict[str, str] = Field(default_factory=dict)
    license: dict[str, str] | str | None = None


def parse_pyproject(root: Path) -> ProjectContext:
    """Read pyproject.toml under root and return typed project metadata.

    Returns an empty ProjectContext if pyproject.toml is missing, unreadable, or invalid."""
    toml_path = root / "pyproject.toml"
    if not toml_path.exists():
        logger.debug("parse_pyproject: no pyproject.toml at %s", root)
        return ProjectContext()
    try:
        with toml_path.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        logger.warning("parse_pyproject: failed to read %s: %s", toml_path, exc)
        return ProjectContext()

    raw_project = data.get("project", {})
    if not isinstance(raw_project, dict):
        return ProjectContext()

    project = _PyprojectProject.model_validate(raw_project)

    license_id: str | None = None
    if isinstance(project.license, dict):
        license_id = project.license.get("text") or project.license.get("expression")
    elif isinstance(project.license, str):
        license_id = project.license

    return ProjectContext(
        name=project.name,
        version=project.version,
        description=project.description,
        dependencies=project.dependencies,
        cli_scripts=project.scripts,
        license_id=license_id,
    )


def build_dir_tree(target: Path, max_depth: int = 2) -> str:
    """Build a depth-limited directory tree string."""
    lines: list[str] = []
    _collect_tree(target, 0, max_depth, "", lines)
    return "\n".join(lines)


def _collect_tree(path: Path, depth: int, max_depth: int, prefix: str, out: list[str]) -> None:
    """Recursively collect directory and file names into out, respecting max_depth."""
    if depth >= max_depth:
        return
    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except PermissionError:
        return
    for entry in entries:
        if entry.name in NOISE_DIRS or entry.name.endswith(".egg-info"):
            continue
        if entry.is_dir():
            out.append(f"{prefix}{entry.name}/")
            _collect_tree(entry, depth + 1, max_depth, prefix + "  ", out)
        else:
            out.append(f"{prefix}{entry.name}")


def find_init_docstring(target: Path) -> str | None:
    """Return the module docstring from an `__init__.py` file directly under the target path."""
    init = target / "__init__.py"
    if not init.exists():
        return None
    try:
        source = init.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return ast.get_docstring(tree)


def load_existing_readme(path: Path, max_chars: int = MAX_README_CHARS) -> tuple[str | None, bool]:
    """Load README content, compacting it when it exceeds max_chars.

    Returns:
        Tuple of (content or None, was_truncated)."""
    if not path.exists():
        return None, False
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None, False
    if len(content) > max_chars:
        return compact_readme(content, max_chars), True
    return content, False


def _docstring_summary(node: _NamedNode) -> str | None:
    """Return the first line of a node's docstring, or None if absent."""
    doc = ast.get_docstring(node)
    if not doc:
        return None
    return doc.splitlines()[0].strip()


def _fmt_symbol(name: str, node: _NamedNode) -> str:
    """Format a symbol as 'name — summary' or just 'name' when no summary exists."""
    summary = _docstring_summary(node)
    return f"{name} — {summary}" if summary else name


def _extract_public_symbols(path: Path) -> list[str]:
    """Return public symbols from a Python file as 'name — summary' strings.

    Respects __all__ if defined. Otherwise includes top-level functions, classes, and
    constants not starting with an underscore."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as _:
        return []

    top_level: dict[str, _NamedNode] = {
        node.name: node for node in ast.iter_child_nodes(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        names = [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
                        return [_fmt_symbol(n, top_level[n]) if n in top_level else n for n in names]

    return [_fmt_symbol(name, node) for name, node in top_level.items() if not name.startswith("_")]


def scan_public_api(target: Path) -> dict[str, list[str]]:
    """Extract exported public symbols from Python files under target.

    Files in NOISE_DIRS or starting with _ (except __init__.py) are excluded."""
    result: dict[str, list[str]] = {}
    for py_file in sorted(target.rglob("*.py")):
        if any(part in NOISE_DIRS for part in py_file.parts):
            continue
        if py_file.stem.startswith("_") and py_file.stem != "__init__":
            continue
        symbols = _extract_public_symbols(py_file)
        if symbols:
            result[str(py_file.relative_to(target))] = symbols
    return result
