"""Tests for changelog_format — pure functions, no mocking required."""

from src.utils.changelog_format import detect_breaking_changes, truncate_diff

# ---------------------------------------------------------------------------
# truncate_diff
# ---------------------------------------------------------------------------


def test_truncate_diff_under_cap_unchanged() -> None:
    diff = "small diff"
    result, truncated = truncate_diff(diff, cap=100)
    assert result == diff
    assert truncated is False


def test_truncate_diff_over_cap_truncates_and_adds_note() -> None:
    diff = "x" * 200
    result, truncated = truncate_diff(diff, cap=100)
    assert truncated is True
    assert result.startswith("x" * 100)
    assert "truncated" in result
    assert "200" in result


def test_truncate_diff_exactly_at_cap_unchanged() -> None:
    diff = "x" * 50
    result, truncated = truncate_diff(diff, cap=50)
    assert result == diff
    assert truncated is False


# ---------------------------------------------------------------------------
# detect_breaking_changes — Conventional Commit markers
# ---------------------------------------------------------------------------


def test_detect_breaking_changes_bang_suffix() -> None:
    commits = ["a1b2c3d feat!: remove public API"]
    assert detect_breaking_changes(commits, "") is True


def test_detect_breaking_changes_scoped_bang() -> None:
    commits = ["a1b2c3d refactor(api)!: drop legacy endpoint"]
    assert detect_breaking_changes(commits, "") is True


def test_detect_breaking_changes_breaking_change_footer() -> None:
    commits = ["a1b2c3d feat: new auth BREAKING CHANGE: session tokens removed"]
    assert detect_breaking_changes(commits, "") is True


# ---------------------------------------------------------------------------
# detect_breaking_changes — diff scan fallback
# ---------------------------------------------------------------------------


def test_detect_breaking_changes_removed_public_def() -> None:
    diff = "-def public_fn():\n+# removed\n"
    assert detect_breaking_changes([], diff) is True


def test_detect_breaking_changes_removed_public_class() -> None:
    diff = "-class PublicClient:\n+# removed\n"
    assert detect_breaking_changes([], diff) is True


def test_detect_breaking_changes_false_on_private_removal() -> None:
    diff = "-def _internal_helper():\n"
    assert detect_breaking_changes([], diff) is False


def test_detect_breaking_changes_false_on_no_signals() -> None:
    commits = ["a1b2c3d fix: handle edge case", "b2c3d4e chore: update deps"]
    diff = "+def new_helper():\n+    pass\n"
    assert detect_breaking_changes(commits, diff) is False


def test_detect_breaking_changes_false_on_removed_method() -> None:
    # Indented method removal — not top-level, not breaking by diff scan
    diff = "-    def internal_method(self):\n"
    assert detect_breaking_changes([], diff) is False
