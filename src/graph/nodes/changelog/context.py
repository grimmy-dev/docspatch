"""clg_context node — collects git diff, commit log, and project version."""

from src.schemas.changelog_io import ChangelogContextUpdate
from src.schemas.changelog_state import ChangelogState
from src.utils.changelog_format import detect_breaking_changes, truncate_diff
from src.utils.changelog_git import (
    get_commit_log,
    get_git_diff,
    get_initial_commit_context,
    is_initial_commit,
)
from src.utils.config import load
from src.utils.diff_semantics import filter_diff_noise, score_and_filter_commits
from src.utils.git import get_repo, get_root
from src.utils.log import get_logger
from src.utils.project_parse import parse_pyproject

logger = get_logger(__name__)


def clg_context(state: ChangelogState) -> ChangelogContextUpdate:
    """Collect git diff, commit log, and project version for the changelog pipeline."""
    repo = get_repo(state.repo_path)
    root = get_root(repo)
    ctx = parse_pyproject(root)
    version = ctx.version or "Unreleased"

    if is_initial_commit(repo) and state.from_ref is None:
        initial_ctx = get_initial_commit_context(repo, root)
        return {
            "diff": initial_ctx,
            "commits": [],
            "version": version,
            "is_initial_commit": True,
            "has_breaking_changes": False,
            "diff_was_truncated": False,
            "nothing_to_document": not initial_ctx.strip(),
        }

    cfg = load()
    raw_diff = get_git_diff(repo, state.from_ref, state.to_ref)
    filtered = filter_diff_noise(raw_diff)
    logger.debug("diff filter: dropped %d hunks — %s", filtered["dropped_hunks"], filtered["drop_reasons"])
    diff, was_truncated = truncate_diff(filtered["content"], cfg.defaults.changelog_diff_cap)
    commits = score_and_filter_commits(get_commit_log(repo, state.from_ref, state.to_ref))

    return {
        "diff": diff,
        "commits": commits,
        "version": version,
        "has_breaking_changes": detect_breaking_changes(commits, raw_diff),
        "is_initial_commit": False,
        "diff_was_truncated": was_truncated,
        "nothing_to_document": not raw_diff.strip() and not commits,
    }
