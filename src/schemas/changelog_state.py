"""ChangelogState and type alias for the changelog LangGraph pipeline."""

import operator
from pathlib import Path
from typing import Annotated, Any

from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

__all__ = ["ChangelogState", "CompiledChangelogGraph"]


class ChangelogState(BaseModel):
    """State threaded through every node in the changelog pipeline."""

    # Configuration
    dry_run: bool = False
    style: str = "compact"
    from_ref: str | None = None
    to_ref: str | None = None
    output_path: Path | None = None

    # Paths
    repo_path: Path | None = None

    # Context — populated by clg_context
    diff: str = ""
    commits: list[str] = Field(default_factory=list)
    version: str = "Unreleased"
    has_breaking_changes: bool = False
    is_initial_commit: bool = False
    diff_was_truncated: bool = False
    nothing_to_document: bool = False

    # Pipeline state
    generated_entry: str = ""
    accepted_entry: str | None = None

    # Control
    cancelled: bool = False

    # Accumulating fields — reducers required for LangGraph multi-node accumulation
    token_actual: Annotated[int, operator.add] = 0
    warnings: Annotated[list[str], operator.add] = Field(default_factory=list)

    @property
    def resolved_output_path(self) -> Path:
        """Return write destination for the changelog file.

        Defaults to CHANGELOG.md in the current directory."""
        return self.output_path or Path("CHANGELOG.md")


# Any is required by LangGraph's CompiledStateGraph type parameters — not avoidable.
type CompiledChangelogGraph = CompiledStateGraph[ChangelogState, Any, Any, Any]
