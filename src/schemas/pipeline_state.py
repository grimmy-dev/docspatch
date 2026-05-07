"""Base state shared by all docspatch LangGraph pipelines."""

import operator
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

__all__ = ["PipelineState"]


class PipelineState(BaseModel):
    """Base state threaded through every docspatch pipeline.

    Subclass for pipeline-specific fields. Fields here are identical across
    the docstring, README, and changelog pipelines and carry the same reducers.
    """

    dry_run: bool = False
    style: str = "compact"
    cancelled: bool = False
    repo_path: Path | None = None
    token_actual: Annotated[int, operator.add] = 0
    warnings: Annotated[list[str], operator.add] = Field(default_factory=list)
