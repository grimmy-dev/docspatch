"""
Schemas module for docspatch.

This package defines the core data structures used throughout the application:
- AppConfig: Persistent user settings and API keys.
- FunctionMetadata: The primary data object representing code functions.
- DocpatchState: The global state for the LangGraph documentation pipeline.
- Graph I/O: TypedDicts for type-safe communication between graph nodes.
"""

from src.schemas.config import AppConfig, AppDefaults, AppKeys, ProviderConfig
from src.schemas.function import FunctionMetadata
from src.schemas.graph_io import (
    BatchDocsUpdate,
    BatcherUpdate,
    Checkpointer,
    CollectBatchesUpdate,
    CompiledDocpatchGraph,
    DocpatchGraph,
    FeedbackUpdate,
    FilePickInterrupt,
    GraphConfig,
    ParsedFunctionsUpdate,
    PreviewUpdate,
    RerunDocsUpdate,
    ReviewInterrupt,
    ReviewSessionResult,
    ScannerUpdate,
    SignificantFunctionsUpdate,
    SizeCheckInterrupt,
    SizeCheckUpdate,
)
from src.schemas.pipeline_state import PipelineState
from src.schemas.state import DocpatchState

__all__ = [
    "AppConfig",
    "AppDefaults",
    "AppKeys",
    "BatchDocsUpdate",
    "BatcherUpdate",
    "Checkpointer",
    "CollectBatchesUpdate",
    "CompiledDocpatchGraph",
    "DocpatchGraph",
    "DocpatchState",
    "PipelineState",
    "FeedbackUpdate",
    "FilePickInterrupt",
    "FunctionMetadata",
    "GraphConfig",
    "ParsedFunctionsUpdate",
    "PreviewUpdate",
    "ProviderConfig",
    "RerunDocsUpdate",
    "ReviewInterrupt",
    "ReviewSessionResult",
    "ScannerUpdate",
    "SignificantFunctionsUpdate",
    "SizeCheckInterrupt",
    "SizeCheckUpdate",
]
