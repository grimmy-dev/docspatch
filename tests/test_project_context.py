"""Tests for project_context — pure fns directly, shell fns via tmp_path."""

from pathlib import Path

from src.schemas.readme_io import ProjectContext
from src.utils.project_context import (
    build_dir_tree,
    detect_badges,
    find_init_docstring,
    git_remote_to_https,
    load_existing_readme,
    parse_pyproject,
    preserve_sections,
)

# ---------------------------------------------------------------------------
# git_remote_to_https
# ---------------------------------------------------------------------------


def test_git_remote_to_https_ssh() -> None:
    assert git_remote_to_https("git@github.com:owner/repo.git") == "https://github.com/owner/repo"


def test_git_remote_to_https_ssh_no_dot_git() -> None:
    assert git_remote_to_https("git@github.com:owner/repo") == "https://github.com/owner/repo"


def test_git_remote_to_https_git_proto() -> None:
    assert git_remote_to_https("git://github.com/owner/repo.git") == "https://github.com/owner/repo"


def test_git_remote_to_https_already_https_strips_git() -> None:
    assert git_remote_to_https("https://github.com/owner/repo.git") == "https://github.com/owner/repo"


def test_git_remote_to_https_already_https_unchanged() -> None:
    assert git_remote_to_https("https://github.com/owner/repo") == "https://github.com/owner/repo"


# ---------------------------------------------------------------------------
# preserve_sections
# ---------------------------------------------------------------------------


def test_preserve_sections_no_markers_returns_updated() -> None:
    assert preserve_sections("original content", "updated content") == "updated content"


def test_preserve_sections_restores_kept_block() -> None:
    original = "intro\n<!-- dp-keep -->\ndo not touch\n<!-- /dp-keep -->\noutro"
    updated = "new intro\n<!-- dp-keep -->\nLLM replaced this\n<!-- /dp-keep -->\nnew outro"
    result = preserve_sections(original, updated)
    assert "do not touch" in result
    assert "LLM replaced this" not in result


def test_preserve_sections_multiple_blocks() -> None:
    original = "<!-- dp-keep -->\nA\n<!-- /dp-keep -->\nmid\n<!-- dp-keep -->\nB\n<!-- /dp-keep -->"
    updated = "<!-- dp-keep -->\nX\n<!-- /dp-keep -->\nmid\n<!-- dp-keep -->\nY\n<!-- /dp-keep -->"
    result = preserve_sections(original, updated)
    assert "A" in result and "B" in result
    assert "X" not in result and "Y" not in result


# ---------------------------------------------------------------------------
# detect_badges
# ---------------------------------------------------------------------------


def test_detect_badges_no_remote_returns_empty() -> None:
    assert detect_badges(None, "mypkg", "1.0.0", "MIT") == []


def test_detect_badges_non_github_returns_empty() -> None:
    assert detect_badges("https://gitlab.com/owner/repo", "mypkg", "1.0.0", "MIT") == []


def test_detect_badges_github_with_version_returns_pypi_badge() -> None:
    badges = detect_badges("https://github.com/owner/mypkg", "mypkg", "1.0.0", None)
    assert len(badges) == 1
    assert "pypi/v/mypkg" in badges[0]


def test_detect_badges_github_with_license_returns_license_badge() -> None:
    badges = detect_badges("https://github.com/owner/mypkg", "mypkg", "1.0.0", "MIT")
    assert any("License-MIT" in b for b in badges)


def test_detect_badges_no_version_skips_pypi_badge() -> None:
    badges = detect_badges("https://github.com/owner/mypkg", "mypkg", None, "MIT")
    assert not any("pypi" in b for b in badges)


def test_detect_badges_unknown_license_skips_license_badge() -> None:
    badges = detect_badges("https://github.com/owner/mypkg", "mypkg", "1.0.0", "WTFPL")
    assert not any("License" in b for b in badges)


# ---------------------------------------------------------------------------
# parse_pyproject (shell — uses tmp_path)
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
# build_dir_tree (shell — uses tmp_path)
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
# find_init_docstring (shell — uses tmp_path)
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
# load_existing_readme (shell — uses tmp_path)
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
