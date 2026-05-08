"""ChangelogState and type alias for the changelog LangGraph pipeline."""

from pathlib import Path
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from src.schemas.pipeline_state import PipelineState
from src.schemas.scout_io import ScoutOutput

__all__ = ["ChangelogState", "CompiledChangelogGraph"]


class ChangelogState(PipelineState):
    """State threaded through every node in the changelog pipeline."""

    # Configuration — set by CLI before graph entry
    from_ref: str | None = None
    to_ref: str | None = None
    output_path: Path | None = None

    # Context — written by clg_context
    changed_files: list[str] = Field(default_factory=list)  # .py files changed in range
    commits: list[str] = Field(default_factory=list)
    version: str = "Unreleased"
    project_name: str = ""
    project_description: str | None = None
    has_breaking_changes: bool = False
    is_initial_commit: bool = False
    nothing_to_document: bool = False  # gate for _after_context → skips clg_scout when True

    # Scout + aggregator output — written by clg_scout / clg_aggregator
    scout_output: ScoutOutput | None = None
    aggregated_context: str = ""

    # Pipeline state
    generated_entry: str = ""  # written by: clg_llm
    accepted_entry: str | None = None  # written by: clg_preview

    @property
    def resolved_output_path(self) -> Path:
        """Return write destination for the changelog file.

        Defaults to CHANGELOG.md under repo_path (or cwd if repo_path is unset)."""
        return self.output_path if self.output_path else (self.repo_path or Path(".")) / "CHANGELOG.md"


# Any is required by LangGraph's CompiledStateGraph type parameters — not avoidable.
type CompiledChangelogGraph = CompiledStateGraph[ChangelogState, Any, Any, Any]
