"""readme_diff_filter node — decides if README needs updating based on git diff."""

from src.schemas.readme_io import ReadmeDiffFilterUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.diff.semantics import filter_diff_noise
from src.utils.git.reader import GitReader
from src.utils.log import get_logger

logger = get_logger(__name__)


def readme_diff_filter(state: ReadmeState) -> ReadmeDiffFilterUpdate:
    """Set up_to_date=True when no py files changed or all changes are noise. Populate diff_changed_files otherwise."""
    if state.rewrite:
        return {}

    try:
        reader = GitReader(state.repo_path)
    except RuntimeError as exc:
        logger.debug("readme_diff_filter: cannot open repo: %s", exc)
        return {}

    target = reader.resolve_target(state.target_path)
    changed = reader.get_diff_files(target)

    if not changed:
        if state.existing_readme:
            logger.debug("readme_diff_filter: no py changes, README exists → up_to_date")
            return {"up_to_date": True}
        return {}

    if not state.existing_readme:
        return {}

    # Verify at least one changed file has meaningful (non-noise) hunks.
    # Import-reorders, whitespace, and comment-only edits do not warrant README regeneration.
    try:
        raw_diff = reader.get_raw_diff(target)
        filtered = filter_diff_noise(raw_diff)
        if not filtered["content"].strip():
            logger.debug(
                "readme_diff_filter: %d file(s) changed but all noise (%s) → up_to_date",
                len(changed),
                filtered["drop_reasons"],
            )
            return {"up_to_date": True}
    except Exception as exc:
        logger.debug("readme_diff_filter: noise check failed, proceeding: %s", exc)

    return {"diff_changed_files": changed}
