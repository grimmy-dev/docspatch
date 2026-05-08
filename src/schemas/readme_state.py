"""ReadmeState and TypedDict I/O types for the readme LangGraph pipeline."""

from pathlib import Path
from typing import Any

from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from src.schemas.pipeline_state import PipelineState
from src.schemas.readme_io import ProjectContext
from src.schemas.scout_io import ScoutOutput
from src.utils.git.reader import GitSignals
from src.utils.project.usage import UsageExample

__all__ = ["CompiledReadmeGraph", "ReadmeState"]


class ReadmeState(PipelineState):
    """State threaded through every node in the readme pipeline."""

    # Paths
    rewrite: bool = False
    target_path: Path | None = None  # scope root; defaults to repo_path
    output_path: Path | None = None  # write destination; defaults to target_path/README.md
    repo_root: Path | None = None  # resolved repo root; set by readme_context for scope detection

    # Project context — written by readme_context
    project_context: ProjectContext = Field(default_factory=ProjectContext)
    remote_url: str | None = None
    dir_tree: str = ""
    init_docstring: str | None = None
    existing_readme: str | None = None
    readme_was_truncated: bool = False
    public_api: dict[str, list[str]] = Field(default_factory=dict)

    # Diff-filter state — written by readme_diff_filter
    up_to_date: bool = False  # gate for _after_diff_filter → skips to END when True
    diff_changed_files: list[str] = Field(default_factory=list)

    # Enrichment signals — written by readme_context
    git_signals: GitSignals | None = None
    test_coverage: str = ""
    usage_examples: list[UsageExample] = Field(default_factory=list)

    # Scout + aggregator output
    scout_output: ScoutOutput | None = None
    aggregated_context: str = ""

    # Pipeline state
    generated_readme: str = ""  # written by: readme_llm
    accepted_readme: str | None = None  # written by: readme_preview
    remarks: str = ""  # set by CLI before graph entry

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
