"""Context signals for README generation — git history, test coverage, diff detection."""

from __future__ import annotations

import ast
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.utils.log import get_logger

if TYPE_CHECKING:
    import git

logger = get_logger(__name__)

__all__ = ["extract_readme_headings", "get_diff_files", "get_git_signals", "get_test_coverage_summary"]


def get_git_signals(repo: git.Repo) -> str:
    """Return a compact git history and activity summary. Empty string on any failure."""
    try:
        count = int(repo.git.rev_list("--count", "HEAD").strip())
        last = repo.git.log("-1", "--format=%ci", "HEAD").strip()[:7]
        first = repo.git.log("--reverse", "-1", "--format=%ci", "HEAD").strip()[:7]
        last_dt = datetime.strptime(last, "%Y-%m")
        now = datetime.now()
        months_since = (now.year - last_dt.year) * 12 + (now.month - last_dt.month)
        status = "dormant" if months_since > 12 else "active"
        return f"Commits: {count} · First: {first} · Last: {last} · Status: {status}"
    except Exception as exc:  # noqa: BLE001 — git may be absent or repo malformed
        logger.debug("get_git_signals failed: %s", exc)
        return ""


_TEST_NAMES_PER_MODULE = 6


def get_test_coverage_summary(root: Path) -> str:
    """Return test function names grouped by module as plain-english behaviour signals.

    Caps at _TEST_NAMES_PER_MODULE names per module. Uses rglob to find nested test dirs.
    Empty string when no tests found."""
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return ""
    modules: dict[str, list[str]] = {}
    for test_file in sorted(tests_dir.rglob("test_*.py")):
        try:
            tree = ast.parse(test_file.read_text(encoding="utf-8"))
        except (OSError, SyntaxError) as _:
            continue
        names = [
            node.name.removeprefix("test_").replace("_", " ")
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        ]
        if names:
            module_name = test_file.stem.removeprefix("test_").replace("_", " ").title()
            modules[module_name] = names[:_TEST_NAMES_PER_MODULE]
    if not modules:
        return ""
    parts = "; ".join(f"{mod}: {', '.join(names)}" for mod, names in modules.items())
    return f"Tests — {parts}"


def get_diff_files(repo: git.Repo, target: Path) -> list[str]:
    """Return Python files under target that differ from HEAD. Empty list on failure."""
    try:
        output = repo.git.diff("HEAD", "--name-only", "--", str(target))
        return [f for f in output.strip().splitlines() if f.endswith(".py")]
    except Exception as exc:  # noqa: BLE001
        logger.debug("get_diff_files failed: %s", exc)
        return []


def extract_readme_headings(readme: str) -> list[str]:
    """Return ## and ### level heading text from a Markdown README. Pure."""
    return [re.sub(r"^#+\s*", "", line).strip() for line in readme.splitlines() if re.match(r"^#{2,3}\s", line)]
