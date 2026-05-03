"""Type aliases and TypedDicts for LangGraph node I/O boundaries."""

from pathlib import Path
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.state import CompiledStateGraph, StateGraph

from src.schemas.function import FunctionMetadata
from src.schemas.state import DocpatchState

type Checkpointer = BaseCheckpointSaver[Any] | AsyncSqliteSaver | MemorySaver
type DocpatchGraph = StateGraph[DocpatchState]
type CompiledDocpatchGraph = CompiledStateGraph[DocpatchState, Any, Any, Any]
type StreamPayload = dict[str, dict[str, object] | list[object]]
type GraphConfig = RunnableConfig


class SizeCheckInterrupt(TypedDict):
    type: str
    file_count: int
    threshold: int
    token_estimate: int


class FilePickInterrupt(TypedDict):
    type: str
    files: list[str]


class ReviewInterrupt(TypedDict):
    type: str
    docs: dict[str, str]


class ScannerUpdate(TypedDict):
    changed_files: list[Path]


class ParsedFunctionsUpdate(TypedDict):
    catalog: dict[str, FunctionMetadata]


class SignificantFunctionsUpdate(TypedDict):
    significant_functions: list[str]
    catalog: dict[str, FunctionMetadata]


class RerunDocsUpdate(TypedDict, total=False):
    generated_docs: dict[str, str]
    token_actual: int
    warnings: list[str]


class SizeCheckUpdate(TypedDict):
    batch_strategy: str
    significant_functions: list[str]


class BatcherUpdate(TypedDict):
    batches: list[list[str]]
    warnings: list[str]


class BatchDocsUpdate(TypedDict):
    generated_docs: dict[str, str]
    token_actual: int


class CollectBatchesUpdate(TypedDict):
    pass


class PreviewUpdate(TypedDict, total=False):
    accepted_docs: dict[str, str]
    rerun_docs: list[str]
    feedback: dict[str, str]


class FeedbackUpdate(TypedDict):
    feedback: dict[str, str]


class ReviewSessionResult(TypedDict):
    accepted: dict[str, str]
    rerun: list[str]
    feedback: dict[str, str]
