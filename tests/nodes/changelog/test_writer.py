"""Tests for clg_writer — prepend logic and atomic write behaviour."""

from pathlib import Path
from unittest.mock import patch

from src.schemas.changelog_state import ChangelogState


def _state(**kwargs: object) -> ChangelogState:
    return ChangelogState(**kwargs)  # type: ignore[arg-type]


def test_dry_run_skips_write(tmp_path: Path) -> None:
    from src.graph.nodes.changelog.writer import clg_writer

    output = tmp_path / "CHANGELOG.md"
    result = clg_writer(_state(dry_run=True, accepted_entry="## New", output_path=output))
    assert result == {}
    assert not output.exists()


def test_no_accepted_entry_skips_write(tmp_path: Path) -> None:
    from src.graph.nodes.changelog.writer import clg_writer

    output = tmp_path / "CHANGELOG.md"
    result = clg_writer(_state(accepted_entry=None, output_path=output))
    assert result == {}
    assert not output.exists()


def test_creates_fresh_changelog_when_none_exists(tmp_path: Path) -> None:
    from src.graph.nodes.changelog.writer import clg_writer

    output = tmp_path / "CHANGELOG.md"
    clg_writer(_state(accepted_entry="## [1.0.0]\n- Added thing", output_path=output))
    assert output.read_text() == "## [1.0.0]\n- Added thing"


def test_prepends_to_existing_changelog(tmp_path: Path) -> None:
    from src.graph.nodes.changelog.writer import clg_writer

    output = tmp_path / "CHANGELOG.md"
    output.write_text("## [0.9.0]\n- Old entry")
    clg_writer(_state(accepted_entry="## [1.0.0]\n- New entry", output_path=output))
    content = output.read_text()
    assert content.startswith("## [1.0.0]")
    assert "## [0.9.0]" in content
    assert content.index("## [1.0.0]") < content.index("## [0.9.0]")


def test_entries_separated_by_blank_line(tmp_path: Path) -> None:
    from src.graph.nodes.changelog.writer import clg_writer

    output = tmp_path / "CHANGELOG.md"
    output.write_text("## [0.9.0]\n- Old")
    clg_writer(_state(accepted_entry="## [1.0.0]\n- New", output_path=output))
    assert "\n\n" in output.read_text()


def test_write_failure_returns_warning(tmp_path: Path) -> None:
    from src.graph.nodes.changelog.writer import clg_writer

    output = tmp_path / "CHANGELOG.md"
    with patch("src.graph.nodes.changelog.writer.atomic_write", side_effect=OSError("disk full")):
        result = clg_writer(_state(accepted_entry="## New", output_path=output))
    assert any("disk full" in w for w in result.get("warnings", []))


def test_read_failure_returns_warning(tmp_path: Path) -> None:
    from src.graph.nodes.changelog.writer import clg_writer

    output = tmp_path / "CHANGELOG.md"
    output.write_text("existing content")
    output.chmod(0o000)
    try:
        result = clg_writer(_state(accepted_entry="## New", output_path=output))
        assert result.get("warnings")
    finally:
        output.chmod(0o644)
