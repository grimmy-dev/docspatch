"""readme_writer node — writes accepted README to disk."""

from src.schemas.readme_io import ReadmeWriterUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.fs import atomic_write
from src.utils.log import get_logger
from src.utils.project_context import preserve_sections

logger = get_logger(__name__)


def readme_writer(state: ReadmeState) -> ReadmeWriterUpdate:
    """Write accepted README to disk, restoring any dp-keep sections first."""
    if state.dry_run or not state.accepted_readme:
        return {}

    content = state.accepted_readme

    if state.existing_readme and not state.rewrite:
        content = preserve_sections(state.existing_readme, content)

    output = state.resolved_output_path

    try:
        atomic_write(output, content)
        logger.debug("readme_writer: wrote %d chars to %s", len(content), output)
    except OSError as exc:
        return {"warnings": [f"Failed to write {output.name}: {exc}"]}

    return {}
