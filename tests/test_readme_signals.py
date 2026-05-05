"""Tests for readme_signals — git signals, test coverage summary, diff detection, headings."""

from pathlib import Path
from unittest.mock import MagicMock

from src.utils.readme_signals import (
    extract_readme_headings,
    get_diff_files,
    get_git_signals,
    get_test_coverage_summary,
)

# ---------------------------------------------------------------------------
# get_test_coverage_summary
# ---------------------------------------------------------------------------


def test_returns_empty_when_no_tests_dir(tmp_path: Path) -> None:
    assert get_test_coverage_summary(tmp_path) == ""


def test_returns_function_names_as_behaviour_signals(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_scanner.py").write_text("def test_returns_empty_list(): pass\ndef test_skips_noise_dirs(): pass\n")
    result = get_test_coverage_summary(tmp_path)
    assert result.startswith("Tests —")
    assert "returns empty list" in result
    assert "skips noise dirs" in result


def test_strips_test_prefix_and_replaces_underscores(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_foo.py").write_text("def test_handles_empty_input(): pass\n")
    result = get_test_coverage_summary(tmp_path)
    assert "handles empty input" in result
    assert "test_" not in result


def test_caps_names_per_module_at_six(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    fns = "\n".join(f"def test_fn_{i}(): pass" for i in range(10))
    (tests_dir / "test_big.py").write_text(fns)
    result = get_test_coverage_summary(tmp_path)
    assert "fn 6" not in result
    assert "fn 9" not in result


def test_handles_nested_test_dirs(tmp_path: Path) -> None:
    unit_dir = tmp_path / "tests" / "unit"
    unit_dir.mkdir(parents=True)
    (unit_dir / "test_parser.py").write_text("def test_parses_function(): pass\n")
    result = get_test_coverage_summary(tmp_path)
    assert "parses function" in result


def test_skips_unparseable_files(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_bad.py").write_text("this is not python ][")
    (tests_dir / "test_good.py").write_text("def test_works(): pass\n")
    result = get_test_coverage_summary(tmp_path)
    assert "works" in result


def test_returns_empty_when_no_test_functions_found(tmp_path: Path) -> None:
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_empty.py").write_text("# no test functions here\n")
    assert get_test_coverage_summary(tmp_path) == ""


# ---------------------------------------------------------------------------
# extract_readme_headings
# ---------------------------------------------------------------------------


def test_extracts_h2_and_h3_headings() -> None:
    readme = "# Title\n## Installation\n### Step One\nSome text.\n## Usage\n"
    assert extract_readme_headings(readme) == ["Installation", "Step One", "Usage"]


def test_skips_h1_and_h4_plus_headings() -> None:
    readme = "# Top\n#### Deep\n## Kept\n"
    assert extract_readme_headings(readme) == ["Kept"]


def test_returns_empty_list_on_no_headings() -> None:
    assert extract_readme_headings("No headings here.") == []


# ---------------------------------------------------------------------------
# get_diff_files
# ---------------------------------------------------------------------------


def test_returns_py_files_from_diff(tmp_path: Path) -> None:
    repo: MagicMock = MagicMock()
    repo.git.diff.return_value = "src/foo.py\nsrc/bar.py\n"
    assert get_diff_files(repo, tmp_path) == ["src/foo.py", "src/bar.py"]


def test_filters_non_py_files(tmp_path: Path) -> None:
    repo: MagicMock = MagicMock()
    repo.git.diff.return_value = "src/foo.py\nREADME.md\nsrc/bar.ts\n"
    assert get_diff_files(repo, tmp_path) == ["src/foo.py"]


def test_diff_returns_empty_on_exception(tmp_path: Path) -> None:
    repo: MagicMock = MagicMock()
    repo.git.diff.side_effect = Exception("git error")
    assert get_diff_files(repo, tmp_path) == []


# ---------------------------------------------------------------------------
# get_git_signals
# ---------------------------------------------------------------------------


def test_git_signals_returns_formatted_summary() -> None:
    repo: MagicMock = MagicMock()
    repo.git.rev_list.return_value = "42"
    repo.git.log.side_effect = ["2026-04-01", "2022-01-01"]
    result = get_git_signals(repo)
    assert "Commits: 42" in result
    assert "First:" in result
    assert "Last:" in result
    assert "Status:" in result


def test_git_signals_returns_empty_on_exception() -> None:
    repo: MagicMock = MagicMock()
    repo.git.rev_list.side_effect = Exception("git error")
    assert get_git_signals(repo) == ""
