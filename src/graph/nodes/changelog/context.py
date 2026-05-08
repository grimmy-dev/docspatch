"""clg_context node — collects changed files, commit log, and project version."""

from src.schemas.changelog_io import ChangelogContextUpdate
from src.schemas.changelog_state import ChangelogState
from src.utils.diff.semantics import detect_breaking_changes, filter_diff_noise, score_and_filter_commits
from src.utils.git.reader import GitReader
from src.utils.log import get_logger
from src.utils.project.parse import parse_pyproject

logger = get_logger(__name__)


def clg_context(state: ChangelogState) -> ChangelogContextUpdate:
    """Collect changed Python files, commit log, and project version for the changelog pipeline.

    Raw diff is used internally for breaking-change detection only — never stored in state."""
    reader = GitReader(state.repo_path)
    root = reader.root
    ctx = parse_pyproject(root)
    version = ctx.version or "Unreleased"

    if reader.is_initial_commit() and state.from_ref is None:
        return {
            "changed_files": [],
            "commits": [],
            "version": version,
            "project_name": ctx.name,
            "project_description": ctx.description,
            "is_initial_commit": True,
            "has_breaking_changes": False,
            "nothing_to_document": False,
        }

    raw_diff = reader.get_diff(state.from_ref, state.to_ref)
    filtered = filter_diff_noise(raw_diff)
    logger.debug("diff filter: dropped %d hunks — %s", filtered["dropped_hunks"], filtered["drop_reasons"])

    changed_files = reader.get_diff_changed_files(state.from_ref, state.to_ref)
    commits = score_and_filter_commits(reader.get_commit_log(state.from_ref, state.to_ref))

    return {
        "changed_files": changed_files,
        "commits": commits,
        "version": version,
        "project_name": ctx.name,
        "project_description": ctx.description,
        "has_breaking_changes": detect_breaking_changes(commits, raw_diff),
        "is_initial_commit": False,
        "nothing_to_document": not raw_diff.strip() and not commits,
    }
