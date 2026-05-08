"""Types and TypedDict I/O boundaries for the readme pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from src.utils.git.reader import GitSignals
from src.utils.project.usage import UsageExample

__all__ = [
    "ProjectContext",
    "ReadmeContextUpdate",
    "ReadmeDiffFilterUpdate",
    "ReadmeLLMUpdate",
    "ReadmePreviewUpdate",
    "ReadmeUnderstandUpdate",
    "ReadmeWriterUpdate",
    "UnderstandCache",
]


@dataclass
class UnderstandCache:
    """Per-module summaries and content hashes produced by readme_understand."""

    summaries: dict[str, str] = field(default_factory=dict)
    hashes: dict[str, str] = field(default_factory=dict)


@dataclass
class ProjectContext:
    """Parsed pyproject.toml metadata — typed container for project-level metadata."""

    name: str = ""
    version: str | None = None
    description: str | None = None
    dependencies: list[str] = field(default_factory=list)
    cli_scripts: dict[str, str] = field(default_factory=dict)
    license_id: str | None = None


class ReadmeContextUpdate(TypedDict, total=False):
    """Returned by readme_context."""

    project_context: ProjectContext
    remote_url: str | None
    dir_tree: str
    init_docstring: str | None
    existing_readme: str | None
    readme_was_truncated: bool
    public_api: dict[str, list[str]]
    git_signals: GitSignals | None
    test_coverage: str
    usage_examples: list[UsageExample]
    repo_root: Path | None
    warnings: list[str]


class ReadmeDiffFilterUpdate(TypedDict, total=False):
    """Returned by readme_diff_filter."""

    up_to_date: bool
    diff_changed_files: list[str]


class ReadmeLLMUpdate(TypedDict):
    """Returned by readme_llm."""

    generated_readme: str
    token_actual: int


class ReadmePreviewUpdate(TypedDict, total=False):
    """Returned by readme_preview after user review."""

    accepted_readme: str | None


class ReadmeWriterUpdate(TypedDict, total=False):
    """Returned by readme_writer."""

    warnings: list[str]


class ReadmeUnderstandUpdate(TypedDict, total=False):
    """Returned by readme_understand."""

    project_understanding: str | None
    understand_cache: UnderstandCache
    token_actual: int
