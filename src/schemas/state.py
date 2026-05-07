"""Shared LangGraph state and reducers for the docstring pipeline."""

from pathlib import Path
from typing import Annotated

__all__ = ["DocpatchState", "merge_dicts"]

from pydantic import Field

from src.schemas.function import FunctionMetadata
from src.schemas.pipeline_state import PipelineState


def merge_dicts(a: dict[str, str], b: dict[str, str]) -> dict[str, str]:
    """Reducer: Right-side wins on key conflict for dictionaries.

    Args:
        a (dict[str, str]): The left dictionary.
        b (dict[str, str]): The right dictionary.

    Returns:
        dict[str, str]: A new dictionary containing all key-value pairs from both `a` and `b`,
            with values from `b` overwriting values from `a` in case of key conflicts."""
    return {**a, **b}


class DocpatchState(PipelineState):
    """Shared state threaded through every docspatch LangGraph node."""

    # Accumulating fields — merged by reducer across parallel docwriter_single batches
    generated_docs: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)  # written by: docwriter_single, docwriter_rerun
    accepted_docs: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)   # written by: docs_preview
    feedback: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)         # written by: docs_preview

    # Configuration — set by CLI before graph entry
    from_ref: str | None = None
    update_all: bool = False

    # Paths — set by CLI before graph entry
    target_path: Path | None = None
    output_path: Path | None = None

    # Pipeline state — written by nodes in pipeline order
    changed_files: list[Path] = Field(default_factory=list)         # scanner → filtered by file_hash_check
    catalog: dict[str, FunctionMetadata] = Field(default_factory=dict)  # libcst_parser → function_hash_check → significance (pruned)
    significant_functions: list[str] = Field(default_factory=list)  # significance → trimmed by size_check
    batches: list[list[str]] = Field(default_factory=list)          # batcher
    current_batch: list[str] = Field(default_factory=list)          # batcher (injected per Send fan-out branch)
    batch_strategy: str = "auto"                                     # size_check
    rerun_docs: list[str] = Field(default_factory=list)             # docs_preview
    error: str | None = None
