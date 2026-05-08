"""TypedDict I/O boundaries for the changelog pipeline."""

from typing import TypedDict

from src.schemas.scout_io import ScoutOutput

__all__ = [
    "ChangelogAggregatorUpdate",
    "ChangelogContextUpdate",
    "ChangelogLLMUpdate",
    "ChangelogPreviewUpdate",
    "ChangelogScoutUpdate",
    "ChangelogWriterUpdate",
]


class ChangelogContextUpdate(TypedDict, total=False):
    """Returned by clg_context."""

    changed_files: list[str]
    commits: list[str]
    version: str
    project_name: str
    project_description: str | None
    has_breaking_changes: bool
    is_initial_commit: bool
    nothing_to_document: bool
    warnings: list[str]


class ChangelogScoutUpdate(TypedDict, total=False):
    """Returned by clg_scout."""

    scout_output: ScoutOutput
    token_actual: int


class ChangelogAggregatorUpdate(TypedDict, total=False):
    """Returned by clg_aggregator."""

    aggregated_context: str


class ChangelogLLMUpdate(TypedDict):
    """Returned by clg_llm."""

    generated_entry: str
    token_actual: int


class ChangelogPreviewUpdate(TypedDict, total=False):
    """Returned by clg_preview after user review."""

    accepted_entry: str | None


class ChangelogWriterUpdate(TypedDict, total=False):
    """Returned by clg_writer."""

    warnings: list[str]
