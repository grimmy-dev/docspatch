"""Types and TypedDict I/O boundaries for the readme pipeline."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

__all__ = [
    "ProjectContext",
    "ReadmeContextUpdate",
    "ReadmeDiffFilterUpdate",
    "ReadmeLLMUpdate",
    "ReadmePreviewUpdate",
    "ReadmeReviewInterrupt",
    "ReadmeWriterUpdate",
]


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

    project_name: str
    project_version: str | None
    project_description: str | None
    dependencies: list[str]
    cli_scripts: dict[str, str]
    remote_url: str | None
    dir_tree: str
    init_docstring: str | None
    existing_readme: str | None
    readme_was_truncated: bool
    license_id: str | None
    public_api: dict[str, list[str]]
    git_signals: str
    test_coverage: str
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


class ReadmeReviewInterrupt(TypedDict):
    """Interrupt payload passed to the CLI review handler."""

    type: str
    content: str
