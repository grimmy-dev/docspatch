"""Project metadata extraction and pure context utilities for dp readme."""

import ast
import re
import tomllib
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.readme_io import ProjectContext
from src.utils.log import get_logger

logger = get_logger(__name__)

MAX_README_CHARS = 4000

NOISE_DIRS: frozenset[str] = frozenset({".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", "dist", "build"})

# Shields.io badge info for known SPDX license IDs
_LICENSE_BADGES: dict[str, tuple[str, str]] = {
    "MIT": ("MIT-yellow", "https://opensource.org/licenses/MIT"),
    "Apache-2.0": ("Apache%202.0-blue", "https://www.apache.org/licenses/LICENSE-2.0"),
    "GPL-3.0": ("GPL%20v3-blue", "https://www.gnu.org/licenses/gpl-3.0"),
    "GPL-3.0-only": ("GPL%20v3-blue", "https://www.gnu.org/licenses/gpl-3.0"),
    "BSD-3-Clause": ("BSD%203--Clause-blue", "https://opensource.org/licenses/BSD-3-Clause"),
    "LGPL-3.0": ("LGPL%20v3-blue", "https://www.gnu.org/licenses/lgpl-3.0"),
}

_GITHUB_SLUG = re.compile(r"https://github\.com/([^/]+/[^/.]+)")
_KEEP_PATTERN = re.compile(r"<!-- dp-keep -->.*?<!-- /dp-keep -->", re.DOTALL)


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
    """Build a depth-limited directory tree string.

    Args:
        target: The root directory path to build the tree from.
        max_depth: The maximum depth of the directory tree to include.

    Returns:
        A string representing the directory tree."""
    lines: list[str] = []
    _collect_tree(target, 0, max_depth, "", lines)
    return "\n".join(lines)


def _collect_tree(path: Path, depth: int, max_depth: int, prefix: str, out: list[str]) -> None:
    """Recursively collect directory and file names from a path into a list, respecting a maximum depth.

    Args:
        path: The current directory to scan.
        depth: The current recursion depth.
        max_depth: The maximum recursion depth to traverse.
        prefix: The indentation string to prepend to each collected name.
        out: The list to append the collected directory and file names to. Modified in place."""
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


def compact_readme(content: str, max_chars: int) -> str:
    """Compact README to max_chars by keeping preamble, headings, and first paragraphs of each section.

    Falls back to hard truncation when compacted result still exceeds limit."""
    if len(content) <= max_chars:
        return content

    lines = content.splitlines()
    out: list[str] = []
    chars = 0
    seen_heading = False
    in_first_para = False
    saw_content = False

    for line in lines:
        is_heading = line.startswith("#")
        is_blank = not line.strip()

        if is_heading:
            seen_heading = True
            in_first_para = True
            saw_content = False
            if out and out[-1].strip():
                out.append("")
                chars += 1
            out.append(line)
            chars += len(line) + 1
        elif not seen_heading:
            out.append(line)
            chars += len(line) + 1
        elif in_first_para:
            if is_blank and saw_content:
                in_first_para = False
            elif not is_blank:
                saw_content = True
                out.append(line)
                chars += len(line) + 1

        if chars >= max_chars:
            break

    result = "\n".join(out)
    return result[:max_chars] if len(result) > max_chars else result


def load_existing_readme(path: Path, max_chars: int = MAX_README_CHARS) -> tuple[str | None, bool]:
    """Load the content of a README file, compacting it if its length exceeds a specified maximum.

    Args:
        path: The path to the README file.
        max_chars: The maximum number of characters allowed for the loaded content.

    Returns:
        A tuple containing:
        - The README content as a string, or `None` if the file does not exist or cannot be read.
        - A boolean indicating `True` if the content was compacted, `False` otherwise."""
    if not path.exists():
        return None, False
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None, False
    if len(content) > max_chars:
        return compact_readme(content, max_chars), True
    return content, False


def git_remote_to_https(url: str) -> str:
    """Convert a Git remote URL from SSH or `git://` format to HTTPS, or normalize an existing HTTPS URL."""
    # git@github.com:owner/repo.git → https://github.com/owner/repo
    ssh = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", url)
    if ssh:
        return f"https://{ssh.group(1)}/{ssh.group(2)}"
    # git://github.com/owner/repo.git → https://github.com/owner/repo
    git_proto = re.match(r"git://(.+?)(?:\.git)?$", url)
    if git_proto:
        return f"https://{git_proto.group(1)}"
    # https://github.com/owner/repo.git → strip .git suffix
    https = re.match(r"(https://[^/]+/.+?)(?:\.git)?$", url)
    if https:
        return https.group(1)
    return url


def preserve_sections(original: str, updated: str) -> str:
    """Restore <!-- dp-keep -->...<!-- /dp-keep --> sections from original into updated.

    If no such sections exist in the original content, the updated content is returned unmodified."""
    preserved = [m.group(0) for m in _KEEP_PATTERN.finditer(original)]
    if not preserved:
        return updated
    idx = 0

    def _replace(m: re.Match[str]) -> str:
        nonlocal idx
        if idx < len(preserved):
            block = preserved[idx]
            idx += 1
            return block
        return m.group(0)

    return _KEEP_PATTERN.sub(_replace, updated)


_NamedNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef


def _docstring_summary(node: _NamedNode) -> str | None:
    """Return the first line of a node's docstring.

    Args:
        node: The AST node to inspect.

    Returns:
        The first line of the docstring, stripped of leading/trailing whitespace, or None if no docstring exists."""
    doc = ast.get_docstring(node)
    if not doc:
        return None
    return doc.splitlines()[0].strip()


def _fmt_symbol(name: str, node: _NamedNode) -> str:
    """Format a symbol name with its docstring summary.

    Args:
        name: The name of the symbol.
        node: The AST node representing the symbol.

    Returns:
        The formatted string, e.g., 'symbol_name — docstring summary' or just 'symbol_name' if no summary exists."""
    summary = _docstring_summary(node)
    return f"{name} — {summary}" if summary else name


def _extract_public_symbols(path: Path) -> list[str]:
    """Return public symbols from a Python file as 'name — summary' strings.

    Respects __all__ if defined. Otherwise, includes top-level functions, classes, and constants not starting with an underscore. Symbols are formatted with their first line of docstring if available."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, SyntaxError) as _:
        return []

    top_level: dict[str, _NamedNode] = {
        node.name: node for node in ast.iter_child_nodes(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__all__":
                    if isinstance(node.value, (ast.List, ast.Tuple)):
                        names = [elt.value for elt in node.value.elts if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
                        return [_fmt_symbol(n, top_level[n]) if n in top_level else n for n in names]

    return [_fmt_symbol(name, node) for name, node in top_level.items() if not name.startswith("_")]


def scan_public_api(target: Path) -> dict[str, list[str]]:
    """Extract all exported public symbols from Python files within a target directory.

    Args:
        target: The root directory to scan for Python files.

    Returns:
        A dictionary mapping relative Python file paths to lists of their public symbols. Files in
        `NOISE_DIRS` or starting with `_` (unless `__init__.py`) are excluded."""
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


def detect_badges(
    remote_url: str | None,
    package_name: str | None,
    version: str | None,
    license_id: str | None,
) -> list[str]:
    """Return badge markdown lines for PyPI and license when URLs will resolve.

    Only emits badges with deterministic, verifiable shield.io URLs. Never invents URLs; missing info produces no badge."""
    if not remote_url or not _GITHUB_SLUG.match(remote_url):
        return []
    badges: list[str] = []
    if package_name and version:
        pkg = package_name
        badges.append(f"[![PyPI version](https://img.shields.io/pypi/v/{pkg}.svg)](https://pypi.org/project/{pkg}/)")
    if license_id and license_id in _LICENSE_BADGES:
        label, url = _LICENSE_BADGES[license_id]
        badges.append(f"[![License: {license_id}](https://img.shields.io/badge/License-{label}.svg)]({url})")
    return badges
