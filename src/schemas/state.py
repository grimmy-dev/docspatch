import operator
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from src.schemas.function import FunctionMetadata


def merge_dicts(a: dict[str, str], b: dict[str, str]) -> dict[str, str]:
    """Reducer: Right-side wins on key conflict for dictionaries."""
    return {**a, **b}


class DocpatchState(BaseModel):
    """Shared state threaded through every docspatch LangGraph node."""

    # --- Accumulating fields (reducers) ---
    generated_docs: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)
    accepted_docs: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)
    token_actual: Annotated[int, operator.add] = 0
    feedback: Annotated[dict[str, str], merge_dicts] = Field(default_factory=dict)
    warnings: Annotated[list[str], operator.add] = Field(default_factory=list)

    # --- Configuration ---
    style: str = "compact"
    from_ref: str | None = None
    update_all: bool = False
    dry_run: bool = False
    cancelled: bool = False

    # --- Environment Paths ---
    repo_path: Path | None = None
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
