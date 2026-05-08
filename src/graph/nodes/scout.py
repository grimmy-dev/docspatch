"""Scout node — parallel per-directory file analysis via AST compression and LLM.

Groups Python files by directory, AST-compresses each file, then fires one
LLM call per directory group in parallel. Usable from both README and CLG pipelines.
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel

from src.schemas.scout_io import FileSummary, ScoutMode, ScoutOutput
from src.utils.ast_compress import compress_file
from src.utils.fs import hash_content
from src.utils.llm.caller import acall_llm, is_cancelled
from src.utils.log import get_logger

__all__ = ["scout_node"]

logger = get_logger(__name__)

_IGNORED_DIRS: frozenset[str] = frozenset({
    ".venv", "__pycache__", ".git", ".mypy_cache", "node_modules", ".tox", "dist", "build",
})

_SCOUT_README_SYSTEM = (
    "You are a code analyst. Analyze the provided Python file skeletons from one directory. "
    "For each file, describe what it does and list its key exported symbols. "
    "Be specific to this codebase — no generic descriptions."
)

_SCOUT_CLG_SYSTEM = (
    "You are a code analyst. Analyze the provided Python file skeletons. "
    "For each file, describe what changed and why it matters to users. "
    "Skip trivial edits: renamed variables, removed comments, reformatted lines. "
    "Focus only on behavioural changes."
)


class _FileAnalysis(BaseModel):
    path: str
    summary: str
    key_symbols: list[str]


class _GroupAnalysis(BaseModel):
    files: list[_FileAnalysis]


def _find_python_files(target_path: Path) -> list[Path]:
    """Return .py files under target_path, excluding common ignored directories."""
    result: list[Path] = []
    for f in target_path.rglob("*.py"):
        if not any(part in _IGNORED_DIRS for part in f.parts):
            result.append(f)
    return sorted(result)


def _group_by_directory(files: list[Path], repo_root: Path) -> dict[str, list[Path]]:
    """Group file paths by parent directory, keys relative to repo_root."""
    groups: dict[str, list[Path]] = {}
    for f in files:
        try:
            rel = f.relative_to(repo_root)
        except ValueError:
            rel = Path(f.name)
        dir_key = str(rel.parent)
        groups.setdefault(dir_key, []).append(f)
    return groups


def _build_group_prompt(dir_key: str, file_skeletons: list[tuple[str, str]], mode: ScoutMode) -> str:
    """Build the LLM prompt covering all files in one directory group."""
    mode_instruction = (
        "Describe what each module does in this directory."
        if mode == "readme"
        else "Describe what changed in each file and why it matters to users. Skip trivial edits."
    )
    parts = [f"Directory: {dir_key}", mode_instruction, ""]
    for rel_path, skeleton in file_skeletons:
        parts.append(f"--- {rel_path} ---")
        parts.append(skeleton or "(no parseable content)")
        parts.append("")
    return "\n".join(parts)


async def _analyse_group(
    dir_key: str,
    files: list[Path],
    repo_root: Path,
    mode: ScoutMode,
    model_key: str,
    run_cache: dict[str, FileSummary] | None,
) -> tuple[list[FileSummary], int, int]:
    """AST-compress files in a directory group, skip cached, call LLM for fresh files."""
    all_data: list[tuple[str, str, str]] = []  # (rel_path, skeleton, content_hash)
    for f in files:
        try:
            rel = str(f.relative_to(repo_root))
        except ValueError:
            rel = f.name
        skeleton = compress_file(f) or ""
        all_data.append((rel, skeleton, hash_content(skeleton)))

    cached_summaries: list[FileSummary] = []
    fresh_data: list[tuple[str, str, str]] = []
    cache_hits = 0

    for rel_path, skeleton, content_hash in all_data:
        if run_cache is not None and content_hash in run_cache:
            cached_summaries.append(run_cache[content_hash])
            cache_hits += 1
        else:
            fresh_data.append((rel_path, skeleton, content_hash))

    if not fresh_data:
        return cached_summaries, 0, cache_hits

    file_skeletons = [(rel_path, skeleton) for rel_path, skeleton, _ in fresh_data]
    system = _SCOUT_README_SYSTEM if mode == "readme" else _SCOUT_CLG_SYSTEM
    prompt = _build_group_prompt(dir_key, file_skeletons, mode)

    parsed, _, tokens = await acall_llm(model_key, system, prompt, output_model=_GroupAnalysis)

    fresh_summaries: list[FileSummary] = []
    if parsed is not None:
        analyses = parsed.files
        for i, (rel_path, _, content_hash) in enumerate(fresh_data):
            if i < len(analyses):
                a = analyses[i]
                summary = FileSummary(path=a.path, summary=a.summary, key_symbols=a.key_symbols)
            else:
                summary = FileSummary(path=rel_path, summary="", key_symbols=[])
            if run_cache is not None:
                run_cache[content_hash] = summary
            fresh_summaries.append(summary)
    else:
        for rel_path, _, content_hash in fresh_data:
            summary = FileSummary(path=rel_path, summary="", key_symbols=[])
            if run_cache is not None:
                run_cache[content_hash] = summary
            fresh_summaries.append(summary)

    return cached_summaries + fresh_summaries, tokens, cache_hits


async def scout_node(
    *,
    target_path: Path,
    repo_root: Path,
    mode: ScoutMode,
    changed_files: list[str] | None = None,
    existing_doc: str | None = None,
    model_key: str,
    run_cache: dict[str, FileSummary] | None = None,
) -> ScoutOutput:
    """Analyse Python files grouped by directory with one LLM call per group.

    readme mode: scans all .py files under target_path.
    clg mode: scopes to changed_files list, reads current file state.
    """
    if is_cancelled():
        return ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=0)

    if mode == "clg" and changed_files is not None:
        files = [
            repo_root / f
            for f in changed_files
            if (repo_root / f).suffix == ".py" and (repo_root / f).is_file()
        ]
    else:
        files = _find_python_files(target_path)

    if not files:
        return ScoutOutput(summaries=[], grouped={}, cache_hits=0, tokens_used=0)

    groups = _group_by_directory(files, repo_root)
    dir_keys = list(groups.keys())
    logger.debug("scout_node mode=%s groups=%d files=%d", mode, len(groups), len(files))

    calls = [_analyse_group(dk, groups[dk], repo_root, mode, model_key, run_cache) for dk in dir_keys]
    results = await asyncio.gather(*calls)

    all_summaries: list[FileSummary] = []
    grouped: dict[str, list[FileSummary]] = {}
    total_tokens = 0
    total_hits = 0

    for dir_key, (summaries, tokens, hits) in zip(dir_keys, results, strict=True):
        all_summaries.extend(summaries)
        grouped[dir_key] = summaries
        total_tokens += tokens
        total_hits += hits

    return ScoutOutput(
        summaries=all_summaries,
        grouped=grouped,
        cache_hits=total_hits,
        tokens_used=total_tokens,
    )
