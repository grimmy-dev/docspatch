"""Unit tests for README section targeting — parse, map, and build targeted context."""

from src.utils.readme_signals import (
    build_targeted_readme_context,
    map_files_to_sections,
    parse_readme_sections,
)

_SAMPLE_README = """\
# My Project

A short description.

## Installation

Install with pip.

## CLI

Run `my-tool --help`.

## Contributing

Send a PR.
"""


# ---------------------------------------------------------------------------
# parse_readme_sections
# ---------------------------------------------------------------------------


def test_parse_returns_preamble_and_h2_sections() -> None:
    sections = parse_readme_sections(_SAMPLE_README)
    headings = [h for h, _ in sections]
    assert headings == ["__preamble__", "Installation", "CLI", "Contributing"]


def test_parse_preamble_content_contains_title() -> None:
    sections = parse_readme_sections(_SAMPLE_README)
    preamble_content = sections[0][1]
    assert "# My Project" in preamble_content
    assert "A short description." in preamble_content


def test_parse_section_content_includes_heading_line() -> None:
    sections = parse_readme_sections(_SAMPLE_README)
    installation = next(content for heading, content in sections if heading == "Installation")
    assert installation.startswith("## Installation")
    assert "Install with pip." in installation


def test_parse_readme_with_no_headings_returns_preamble_only() -> None:
    sections = parse_readme_sections("Just some text.\nNo headings here.\n")
    assert len(sections) == 1
    assert sections[0][0] == "__preamble__"


def test_parse_empty_string_returns_empty_list() -> None:
    assert parse_readme_sections("") == []


# ---------------------------------------------------------------------------
# map_files_to_sections
# ---------------------------------------------------------------------------


def test_map_cli_file_matches_cli_heading() -> None:
    matched = map_files_to_sections(["src/cli/commands.py"], ["CLI", "Installation", "Contributing"])
    assert "CLI" in matched


def test_map_commands_file_matches_commands_heading() -> None:
    matched = map_files_to_sections(["src/cli/commands.py"], ["Commands", "Usage", "Installation"])
    assert "Commands" in matched


def test_map_no_overlap_returns_empty_set() -> None:
    matched = map_files_to_sections(["src/utils/cache.py"], ["Installation", "Contributing", "License"])
    assert matched == set()


def test_map_stop_words_excluded_from_matching() -> None:
    # "for" and "the" are stop words and must not cause false matches
    matched = map_files_to_sections(["src/utils/for_the_user.py"], ["Installation"])
    assert "Installation" not in matched


def test_map_multiple_files_can_match_multiple_sections() -> None:
    files = ["src/cli/main.py", "src/utils/install.py"]
    matched = map_files_to_sections(files, ["CLI", "Installation", "Contributing"])
    assert "CLI" in matched
    assert "Installation" in matched
    assert "Contributing" not in matched


def test_map_empty_files_returns_empty_set() -> None:
    assert map_files_to_sections([], ["CLI", "Installation"]) == set()


# ---------------------------------------------------------------------------
# build_targeted_readme_context
# ---------------------------------------------------------------------------


def test_targeted_affected_section_gets_update_prefix() -> None:
    result = build_targeted_readme_context(_SAMPLE_README, ["src/cli/commands.py"])
    assert "[UPDATE] ## CLI" in result


def test_targeted_unaffected_section_gets_keep_prefix_heading_only() -> None:
    result = build_targeted_readme_context(_SAMPLE_README, ["src/cli/commands.py"])
    assert "[KEEP] ## Installation" in result
    # body text of unaffected section must not appear
    assert "Install with pip." not in result


def test_targeted_preamble_always_included_verbatim() -> None:
    result = build_targeted_readme_context(_SAMPLE_README, ["src/cli/commands.py"])
    assert "# My Project" in result
    assert "A short description." in result
    # preamble must NOT be prefixed with [UPDATE] or [KEEP]
    assert "[UPDATE] # My Project" not in result
    assert "[KEEP] # My Project" not in result


def test_targeted_footer_instruction_present() -> None:
    result = build_targeted_readme_context(_SAMPLE_README, ["src/cli/commands.py"])
    assert "[INSTRUCTION]" in result
    assert "[KEEP]" in result
    assert "[UPDATE]" in result


def test_targeted_no_match_returns_original_readme_unchanged() -> None:
    result = build_targeted_readme_context(_SAMPLE_README, ["src/utils/cache.py"])
    assert result == _SAMPLE_README


def test_targeted_empty_readme_returns_empty() -> None:
    assert build_targeted_readme_context("", ["src/cli/main.py"]) == ""


def test_targeted_empty_files_returns_original_readme() -> None:
    result = build_targeted_readme_context(_SAMPLE_README, [])
    assert result == _SAMPLE_README
