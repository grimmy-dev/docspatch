"""Scout node I/O types."""

from typing import Literal, TypedDict

__all__ = ["FileSummary", "ScoutMode", "ScoutOutput"]

ScoutMode = Literal["readme", "clg"]


class FileSummary(TypedDict):
    """Per-file analysis result produced by the scout node."""

    path: str
    summary: str
    key_symbols: list[str]


class ScoutOutput(TypedDict):
    """Aggregated output from the scout node."""

    summaries: list[FileSummary]
    grouped: dict[str, list[FileSummary]]
    cache_hits: int
    tokens_used: int
