"""Pydantic output models for structured LLM responses."""

from pydantic import BaseModel

__all__ = ["BatchDocstringOutput", "DocstringOutput"]


class DocstringOutput(BaseModel):
    """Single function name + generated docstring."""

    name: str
    docstring: str


class BatchDocstringOutput(BaseModel):
    """Batch of docstring outputs returned by the LLM in one call."""

    items: list[DocstringOutput]
