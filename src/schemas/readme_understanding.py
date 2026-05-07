"""Typed models for structured project understanding produced by readme_understand."""

from pydantic import BaseModel

__all__ = ["ModuleUnderstanding", "ProjectUnderstanding"]


class ModuleUnderstanding(BaseModel):
    """Understanding of a single Python module."""

    module_path: str
    purpose: str
    key_components: list[str]
    public_contract: str


class ProjectUnderstanding(BaseModel):
    """Structured understanding of the whole project, assembled from module summaries."""

    primary_purpose: str
    core_components: list[ModuleUnderstanding]
    unique_characteristics: list[str]
    primary_usage_flow: str
