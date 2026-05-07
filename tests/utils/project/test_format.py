"""Tests for project_format — pure functions, no I/O."""

from src.utils.project.format import detect_badges, git_remote_to_https, preserve_sections

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
