"""Tests for project_parse — shell fns exercised via tmp_path."""

from pathlib import Path

from src.schemas.readme_io import ProjectContext
from src.utils.project_api import scan_public_api
from src.utils.project_parse import (
    build_dir_tree,
    find_init_docstring,
    load_existing_readme,
    parse_pyproject,
)

# ---------------------------------------------------------------------------
# parse_pyproject
# ---------------------------------------------------------------------------

PYPROJECT_TOML = """\
[project]
name = "myapp"
version = "0.2.0"
description = "A test app"
dependencies = ["requests>=2.0", "click"]

[project.scripts]
myapp = "myapp.cli:main"

[project.license]
text = "MIT"
"""


def test_parse_pyproject_extracts_fields(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT_TOML)
    ctx = parse_pyproject(tmp_path)
    assert ctx.name == "myapp"
    assert ctx.version == "0.2.0"
    assert ctx.description == "A test app"
    assert "requests>=2.0" in ctx.dependencies
    assert ctx.cli_scripts == {"myapp": "myapp.cli:main"}
    assert ctx.license_id == "MIT"


def test_parse_pyproject_missing_file_returns_empty(tmp_path: Path) -> None:
    ctx = parse_pyproject(tmp_path)
    assert ctx == ProjectContext()


def test_parse_pyproject_malformed_toml_returns_empty(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("this is not valid toml ][")
    ctx = parse_pyproject(tmp_path)
    assert ctx == ProjectContext()


# ---------------------------------------------------------------------------
# build_dir_tree
# ---------------------------------------------------------------------------


def test_build_dir_tree_includes_dirs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    tree = build_dir_tree(tmp_path)
    assert "src/" in tree
    assert "tests/" in tree


def test_build_dir_tree_skips_noise(tmp_path: Path) -> None:
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "src").mkdir()
    tree = build_dir_tree(tmp_path)
    assert "__pycache__" not in tree
    assert "src/" in tree


def test_build_dir_tree_respects_max_depth(tmp_path: Path) -> None:
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    tree = build_dir_tree(tmp_path, max_depth=2)
    assert "a/" in tree
    assert "b/" in tree
    assert "c/" not in tree


def test_build_dir_tree_includes_files_at_level1(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("")
    tree = build_dir_tree(tmp_path)
    assert "pyproject.toml" in tree


# ---------------------------------------------------------------------------
# find_init_docstring
# ---------------------------------------------------------------------------


def test_find_init_docstring_returns_docstring(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text('"""My module."""\n')
    assert find_init_docstring(tmp_path) == "My module."


def test_find_init_docstring_no_init_returns_none(tmp_path: Path) -> None:
    assert find_init_docstring(tmp_path) is None


def test_find_init_docstring_no_docstring_returns_none(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("x = 1\n")
    assert find_init_docstring(tmp_path) is None


# ---------------------------------------------------------------------------
# load_existing_readme
# ---------------------------------------------------------------------------


def test_load_existing_readme_returns_content(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Hello")
    content, truncated = load_existing_readme(tmp_path / "README.md")
    assert content == "# Hello"
    assert truncated is False


def test_load_existing_readme_missing_returns_none(tmp_path: Path) -> None:
    content, truncated = load_existing_readme(tmp_path / "README.md")
    assert content is None
    assert truncated is False


def test_load_existing_readme_truncates_long_content(tmp_path: Path) -> None:
    long_text = "x" * 5000
    (tmp_path / "README.md").write_text(long_text)
    content, truncated = load_existing_readme(tmp_path / "README.md", max_chars=100)
    assert truncated is True
    assert content is not None
    assert len(content) == 100


# ---------------------------------------------------------------------------
# scan_public_api
# ---------------------------------------------------------------------------


def test_scan_public_api_includes_docstring_summary(tmp_path: Path) -> None:
    (tmp_path / "utils.py").write_text('def parse(text: str) -> str:\n    """Parse and return cleaned text."""\n    ...\n')
    api = scan_public_api(tmp_path)
    assert any("parse — Parse and return cleaned text." in s for s in api.get("utils.py", []))


def test_scan_public_api_handles_no_docstring(tmp_path: Path) -> None:
    (tmp_path / "utils.py").write_text("def parse(text: str) -> str: ...\n")
    assert scan_public_api(tmp_path).get("utils.py") == ["parse"]


def test_scan_public_api_respects_all(tmp_path: Path) -> None:
    src = '__all__ = ["public_fn"]\ndef public_fn(): ...\ndef excluded(): ...\n'
    (tmp_path / "mod.py").write_text(src)
    symbols = scan_public_api(tmp_path).get("mod.py", [])
    assert any(s.startswith("public_fn") for s in symbols)
    assert all("excluded" not in s for s in symbols)


def test_scan_public_api_skips_noise_dirs(tmp_path: Path) -> None:
    noise = tmp_path / "__pycache__"
    noise.mkdir()
    (noise / "cached.py").write_text("def fn(): ...\n")
    (tmp_path / "real.py").write_text("def fn(): ...\n")
    api = scan_public_api(tmp_path)
    assert not any("__pycache__" in k for k in api)
    assert any("real.py" in k for k in api)


def test_scan_public_api_skips_private_files(tmp_path: Path) -> None:
    (tmp_path / "_internal.py").write_text("def secret(): ...\n")
    (tmp_path / "public.py").write_text("def exposed(): ...\n")
    api = scan_public_api(tmp_path)
    assert "_internal.py" not in api
    assert "public.py" in api
