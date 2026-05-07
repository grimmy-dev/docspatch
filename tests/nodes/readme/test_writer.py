"""Tests for readme_writer node — mocks atomic_write, verifies preserve_sections wiring."""

from pathlib import Path
from unittest.mock import patch

from src.schemas.readme_state import ReadmeState

_EXISTING = "# Old\n<!-- dp-keep -->kept<!-- /dp-keep -->\nOld content."
_NEW = "# New\n<!-- dp-keep -->replaced<!-- /dp-keep -->\nNew content."


def _state(**kwargs: object) -> ReadmeState:
    return ReadmeState(repo_path=Path("/repo"), target_path=Path("/repo"), **kwargs)  # type: ignore[arg-type]


def test_dry_run_skips_write() -> None:
    from src.graph.nodes.readme.writer import readme_writer

    with patch("src.graph.nodes.readme.writer.atomic_write") as mock_write:
        readme_writer(_state(dry_run=True, accepted_readme="# README"))

    mock_write.assert_not_called()


def test_no_accepted_readme_skips_write() -> None:
    from src.graph.nodes.readme.writer import readme_writer

    with patch("src.graph.nodes.readme.writer.atomic_write") as mock_write:
        readme_writer(_state(accepted_readme=None))

    mock_write.assert_not_called()


def test_preserve_sections_applied_when_existing_and_not_rewrite() -> None:
    from src.graph.nodes.readme.writer import readme_writer

    with patch("src.graph.nodes.readme.writer.atomic_write") as mock_write:
        with patch("src.graph.nodes.readme.writer.preserve_sections", return_value="# Merged") as mock_preserve:
            readme_writer(_state(accepted_readme=_NEW, existing_readme=_EXISTING, rewrite=False))

    mock_preserve.assert_called_once_with(_EXISTING, _NEW)
    mock_write.assert_called_once()
    written_content = mock_write.call_args[0][1]
    assert written_content == "# Merged"


def test_preserve_sections_skipped_on_rewrite() -> None:
    from src.graph.nodes.readme.writer import readme_writer

    with patch("src.graph.nodes.readme.writer.atomic_write") as mock_write:
        with patch("src.graph.nodes.readme.writer.preserve_sections") as mock_preserve:
            readme_writer(_state(accepted_readme=_NEW, existing_readme=_EXISTING, rewrite=True))

    mock_preserve.assert_not_called()
    mock_write.assert_called_once()
    written_content = mock_write.call_args[0][1]
    assert written_content == _NEW


def test_output_path_defaults_to_target_readme() -> None:
    from src.graph.nodes.readme.writer import readme_writer

    with patch("src.graph.nodes.readme.writer.atomic_write") as mock_write:
        readme_writer(_state(accepted_readme="# README"))

    written_path: Path = mock_write.call_args[0][0]
    assert written_path == Path("/repo/README.md")


def test_write_failure_returns_warning() -> None:
    from src.graph.nodes.readme.writer import readme_writer

    with patch("src.graph.nodes.readme.writer.atomic_write", side_effect=OSError("disk full")):
        result = readme_writer(_state(accepted_readme="# README"))

    assert result.get("warnings")
    assert "disk full" in result["warnings"][0]
