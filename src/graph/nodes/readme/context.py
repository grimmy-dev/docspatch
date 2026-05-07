"""readme_context node — collects project context from disk and git."""

from pathlib import Path

from src.schemas.readme_io import ReadmeContextUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.git import get_repo, get_root, resolve_target
from src.utils.log import get_logger
from src.utils.project_format import MAX_README_CHARS, git_remote_to_https
from src.utils.project_api import scan_public_api
from src.utils.project_parse import (
    build_dir_tree,
    find_init_docstring,
    load_existing_readme,
    parse_pyproject,
)
from src.utils.readme_io import get_git_signals, get_test_coverage_summary
from src.utils.usage_signals import extract_usage_examples

logger = get_logger(__name__)


def readme_context(state: ReadmeState) -> ReadmeContextUpdate:
    """Collect project metadata, directory tree, git remote, and existing README."""
    repo = get_repo(state.repo_path)
    root = get_root(repo)
    target = resolve_target(state.target_path, root)

    ctx = parse_pyproject(root)

    try:
        remote_url: str | None = git_remote_to_https(repo.remotes[0].url) if repo.remotes else None
    except (IndexError, AttributeError) as _:
        remote_url = None

    readme_path = Path(state.output_path) if state.output_path else target / "README.md"
    raw_readme, was_truncated = load_existing_readme(readme_path)
    existing_readme = None if state.rewrite else raw_readme

    warnings: list[str] = []
    if was_truncated and not state.rewrite:
        logger.debug("readme_context: README exceeds %d chars, compacted for LLM context", MAX_README_CHARS)

    max_depth = 3 if target != root else 2

    return {
        "project_name": ctx.name,
        "project_version": ctx.version,
        "project_description": ctx.description,
        "dependencies": ctx.dependencies,
        "cli_scripts": ctx.cli_scripts,
        "remote_url": remote_url,
        "dir_tree": build_dir_tree(target, max_depth=max_depth),
        "init_docstring": find_init_docstring(target),
        "existing_readme": existing_readme,
        "readme_was_truncated": was_truncated and not state.rewrite,
        "license_id": ctx.license_id,
        "public_api": scan_public_api(target),
        "git_signals": get_git_signals(repo),
        "test_coverage": get_test_coverage_summary(root),
        "usage_examples": extract_usage_examples(root),
        "repo_root": root,
        "warnings": warnings,
    }
