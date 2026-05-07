"""Tests for diff_semantics — pure functions, no mocking needed."""

from src.utils.diff.semantics import (
    filter_diff_noise,
    score_and_filter_commits,
)

# ---------------------------------------------------------------------------
# Diff fixtures
# ---------------------------------------------------------------------------

_WHITESPACE_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,4 +1,5 @@
 x = 1
+
-
 y = 2
"""

_SIGNATURE_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,3 @@
-def foo():
+def foo(x: int) -> None:
     pass
"""

_COMMENT_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,3 @@
 x = 1
-# old comment
+# new comment
 y = 2
"""

_IMPORT_REORDER_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,3 +1,3 @@
-import os
-import sys
+import sys
+import os
"""

_DOCSTRING_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,5 +1,5 @@
 def foo() -> None:
-    \"\"\"Old docstring.\"\"\"
+    \"\"\"New improved docstring.\"\"\"
     pass
"""

_LOCK_FILE_DIFF = """\
diff --git a/uv.lock b/uv.lock
index abc..def 100644
--- a/uv.lock
+++ b/uv.lock
@@ -1,3 +1,3 @@
-requests==2.28.0
+requests==2.29.0
 urllib3==1.26.0
"""

_TOML_VERSION_DIFF = """\
diff --git a/pyproject.toml b/pyproject.toml
index abc..def 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1,3 +1,3 @@
 [project]
-version = "0.1.0"
+version = "0.2.0"
 name = "mypackage"
"""

_MIXED_DIFF = """\
diff --git a/src/foo.py b/src/foo.py
index abc..def 100644
--- a/src/foo.py
+++ b/src/foo.py
@@ -1,5 +1,5 @@
-# old comment
+# new comment
+result = compute(x)
 y = 2
"""

# ---------------------------------------------------------------------------
# filter_diff_noise tests
# ---------------------------------------------------------------------------


def test_whitespace_only_hunk_dropped() -> None:
    result = filter_diff_noise(_WHITESPACE_DIFF)
    assert result["dropped_hunks"] == 1
    assert "whitespace-only" in result["drop_reasons"]
    assert "src/foo.py" not in result["content"]


def test_signature_hunk_kept() -> None:
    result = filter_diff_noise(_SIGNATURE_DIFF)
    assert result["dropped_hunks"] == 0
    assert "def foo" in result["content"]


def test_comment_only_hunk_dropped() -> None:
    result = filter_diff_noise(_COMMENT_DIFF)
    assert result["dropped_hunks"] == 1
    assert "comment-only" in result["drop_reasons"]


def test_import_reorder_dropped() -> None:
    result = filter_diff_noise(_IMPORT_REORDER_DIFF)
    assert result["dropped_hunks"] == 1
    assert "import-reorder" in result["drop_reasons"]


def test_docstring_only_dropped() -> None:
    result = filter_diff_noise(_DOCSTRING_DIFF)
    assert result["dropped_hunks"] == 1
    assert "docstring-only" in result["drop_reasons"]


def test_noise_file_dropped() -> None:
    result = filter_diff_noise(_LOCK_FILE_DIFF)
    assert result["dropped_hunks"] == 1
    assert "noise-file" in result["drop_reasons"]
    assert "uv.lock" not in result["content"]


def test_toml_version_bump_dropped() -> None:
    result = filter_diff_noise(_TOML_VERSION_DIFF)
    assert result["dropped_hunks"] == 1
    assert "toml-version-bump" in result["drop_reasons"]


def test_mixed_hunk_kept() -> None:
    result = filter_diff_noise(_MIXED_DIFF)
    assert result["dropped_hunks"] == 0
    assert "result = compute" in result["content"]


def test_empty_diff_returns_unchanged() -> None:
    result = filter_diff_noise("")
    assert result["content"] == ""
    assert result["dropped_hunks"] == 0


# ---------------------------------------------------------------------------
# score_and_filter_commits tests
# ---------------------------------------------------------------------------


def test_score_keeps_feat() -> None:
    commits = ["abc1234 feat: add new command"]
    assert score_and_filter_commits(commits) == commits


def test_score_drops_chore() -> None:
    commits = ["abc1234 chore: update deps", "def5678 feat: add thing"]
    result = score_and_filter_commits(commits)
    assert "abc1234 chore: update deps" not in result
    assert "def5678 feat: add thing" in result


def test_score_keeps_breaking_chore() -> None:
    commits = ["abc1234 chore!: drop Python 3.11 support"]
    assert score_and_filter_commits(commits) == commits


def test_score_freeform_kept() -> None:
    commits = ["abc1234 Updated the config for prod"]
    assert score_and_filter_commits(commits) == commits


def test_score_never_empty_fallback() -> None:
    commits = ["abc1234 chore: lint", "def5678 style: format"]
    result = score_and_filter_commits(commits)
    assert result == commits


def test_score_empty_input() -> None:
    assert score_and_filter_commits([]) == []


def test_score_keeps_fix_and_perf() -> None:
    commits = ["abc1234 fix: null check", "def5678 perf: cache result"]
    result = score_and_filter_commits(commits)
    assert result == commits


