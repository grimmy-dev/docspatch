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

    # --- Accumulating fields (reducers) ---
    generated_docs: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)
    accepted_docs: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)
    feedback: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)

    # --- Configuration ---
    from_ref: str | None = None
    update_all: bool = False

    # --- Environment Paths ---
    target_path: Path | None = None
    output_path: Path | None = None

    # --- Pipeline State ---
    changed_files: list[Path] = Field(default_factory=list)
    catalog: dict[str, FunctionMetadata] = Field(default_factory=dict)
    significant_functions: list[str] = Field(default_factory=list)
    batches: list[list[str]] = Field(default_factory=list)
    current_batch: list[str] = Field(default_factory=list)
    batch_strategy: str = "auto"
    rerun_docs: list[str] = Field(default_factory=list)
    error: str | None = None
