"""ReadmeState and TypedDict I/O types for the readme LangGraph pipeline."""

import operator
from pathlib import Path
from typing import Annotated, Any

from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from src.utils.usage_signals import UsageExample

__all__ = ["CompiledReadmeGraph", "ReadmeState"]


class ReadmeState(BaseModel):
    """State threaded through every node in the readme pipeline."""

    # Configuration
    dry_run: bool = False
    rewrite: bool = False
    style: str = "compact"

    # Paths
    repo_path: Path | None = None
    target_path: Path | None = None  # scope root; defaults to repo_path
    output_path: Path | None = None  # write destination; defaults to target_path/README.md
    repo_root: Path | None = None  # resolved repo root; set by readme_context for scope detection

    # Project context — populated by readme_context
    project_name: str = ""
    project_version: str | None = None
    project_description: str | None = None
    dependencies: list[str] = Field(default_factory=list)
    cli_scripts: dict[str, str] = Field(default_factory=dict)
    remote_url: str | None = None
    dir_tree: str = ""
    init_docstring: str | None = None
    existing_readme: str | None = None
    readme_was_truncated: bool = False
    license_id: str | None = None
    public_api: dict[str, list[str]] = Field(default_factory=dict)

    # Diff-filter state — populated by readme_diff_filter
    up_to_date: bool = False
    diff_changed_files: list[str] = Field(default_factory=list)

    # Enrichment signals — populated by readme_context
    git_signals: str = ""
    test_coverage: str = ""
    usage_examples: list[UsageExample] = Field(default_factory=list)

    # Understanding cache — populated by readme_understand
    project_understanding: str | None = None
    module_summaries: dict[str, str] = Field(default_factory=dict)
    module_hashes: dict[str, str] = Field(default_factory=dict)

    # Pipeline state
    generated_readme: str = ""
    accepted_readme: str | None = None
    remarks: str = ""

    # Accumulating fields — reducers required for LangGraph multi-node accumulation
    token_actual: Annotated[int, operator.add] = 0
    warnings: Annotated[list[str], operator.add] = Field(default_factory=list)

    # Control
    cancelled: bool = False

    @property
    def resolved_output_path(self) -> Path:
        """Compute the README write destination.

        The destination is determined by prioritizing `output_path`, then `target_path`, and finally
        defaulting to the repository path or the current directory.

        Returns:
            Path: The computed path for the README file."""
        target = self.target_path if self.target_path else (self.repo_path or Path("."))
        return self.output_path if self.output_path else target / "README.md"


# Any is required by LangGraph's CompiledStateGraph type parameters — not avoidable.
type CompiledReadmeGraph = CompiledStateGraph[ReadmeState, Any, Any, Any]
