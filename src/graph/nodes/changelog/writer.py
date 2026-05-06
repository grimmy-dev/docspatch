"""clg_writer node — prepends accepted changelog entry to CHANGELOG.md."""

from src.schemas.changelog_io import ChangelogWriterUpdate
from src.schemas.changelog_state import ChangelogState
from src.utils.fs import atomic_write
from src.utils.log import get_logger

logger = get_logger(__name__)


def clg_writer(state: ChangelogState) -> ChangelogWriterUpdate:
    """Prepend accepted entry to CHANGELOG.md. Creates the file if absent."""
    if state.dry_run or not state.accepted_entry:
        return {}

    output = state.resolved_output_path
    existing = ""
    if output.exists():
        try:
            existing = output.read_text(encoding="utf-8")
        except OSError as exc:
            return {"warnings": [f"Failed to read {output.name}: {exc}"]}

    content = state.accepted_entry if not existing else f"{state.accepted_entry}\n\n{existing}"

    try:
        atomic_write(output, content)
        logger.debug("clg_writer: wrote %d chars to %s", len(content), output)
    except OSError as exc:
        return {"warnings": [f"Failed to write {output.name}: {exc}"]}

    return {}
