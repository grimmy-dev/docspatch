"""readme_context node — collects project context from disk and git."""

import dataclasses
from pathlib import Path

from src.schemas.readme_io import ProjectContext, ReadmeContextUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.git.reader import GitReader
from src.utils.log import get_logger
from src.utils.project.api import scan_public_api
from src.utils.project.format import MAX_README_CHARS, git_remote_to_https
from src.utils.project.parse import (
    build_dir_tree,
    find_init_docstring,
    load_existing_readme,
    parse_pyproject,
)
from src.utils.project.usage import extract_usage_examples
from src.utils.readme.signals import get_test_coverage_summary

logger = get_logger(__name__)


def _scope_context(ctx: ProjectContext, *, is_subpackage: bool) -> ProjectContext:
    """Strip repo-level fields from context when target is a subpackage."""
    if not is_subpackage:
        return ctx
    return dataclasses.replace(ctx, dependencies=[], cli_scripts={}, license_id=None)


def readme_context(state: ReadmeState) -> ReadmeContextUpdate:
    """Collect project metadata, directory tree, git remote, and existing README."""
    reader = GitReader(state.repo_path)
    root = reader.root
    target = reader.resolve_target(state.target_path)

    is_subpackage = target != root
    ctx = _scope_context(parse_pyproject(root), is_subpackage=is_subpackage)

    raw_remote = reader.get_remote_url()
    remote_url = None if is_subpackage else (git_remote_to_https(raw_remote) if raw_remote else None)

    readme_path = Path(state.output_path) if state.output_path else target / "README.md"
    raw_readme, was_truncated = load_existing_readme(readme_path)
    existing_readme = None if state.rewrite else raw_readme

    warnings: list[str] = []
    if was_truncated and not state.rewrite:
        logger.debug("readme_context: README exceeds %d chars, compacted for LLM context", MAX_README_CHARS)

    max_depth = 3 if is_subpackage else 2

    return {
        "project_context": ctx,
        "remote_url": remote_url,
        "dir_tree": build_dir_tree(target, max_depth=max_depth),
        "init_docstring": find_init_docstring(target),
        "existing_readme": existing_readme,
        "readme_was_truncated": was_truncated and not state.rewrite,
        "public_api": scan_public_api(target),
        "git_signals": reader.get_activity_signals(),
        "test_coverage": get_test_coverage_summary(root),
        "usage_examples": extract_usage_examples(root),
        "repo_root": root,
        "warnings": warnings,
    }
