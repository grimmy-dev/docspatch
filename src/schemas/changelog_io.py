"""TypedDict I/O boundaries for the changelog pipeline."""

from typing import TypedDict

__all__ = [
    "ChangelogContextUpdate",
    "ChangelogLLMUpdate",
    "ChangelogPreviewUpdate",
    "ChangelogReviewInterrupt",
    "ChangelogWriterUpdate",
]


class ChangelogContextUpdate(TypedDict, total=False):
    """Returned by clg_context."""

    diff: str
    commits: list[str]
    version: str
    project_name: str
    project_description: str | None
    has_breaking_changes: bool
    is_initial_commit: bool
    diff_was_truncated: bool
    nothing_to_document: bool
    warnings: list[str]


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


class ChangelogReviewInterrupt(TypedDict):
    """Interrupt payload passed to the CLI review handler."""

    type: str
    content: str
