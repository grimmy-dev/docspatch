"""readme_understand node — cheap per-module summarisation with hash-based caching."""

import asyncio
import hashlib
from pathlib import Path

from src.schemas.readme_io import ReadmeUnderstandUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.config import load
from src.utils.llm import acall_llm, is_cancelled
from src.utils.log import get_logger
from src.utils.prompts import README_UNDERSTAND_SYSTEM

logger = get_logger(__name__)

_COMPACT_MODULE_CAP = 5
_DETAILED_MODULE_CAP = 10
_MAX_CONTENT_LINES = 60

_HIGH_PRIORITY_PARTS: frozenset[str] = frozenset({"cli", "commands"})
_MED_PRIORITY_PARTS: frozenset[str] = frozenset({"nodes", "graph", "utils"})


def _rank_module(path: str, changed: frozenset[str]) -> int:
    """Score a module path for understanding priority. Higher = more important."""
    if path in changed:
        return 3
    p = Path(path)
    if p.stem in {"__main__", "main"}:
        return 3
    parts = frozenset(p.parts)
    if parts & _HIGH_PRIORITY_PARTS:
        return 2
    if parts & _MED_PRIORITY_PARTS:
        return 1
    return 0


def _select_modules(
    public_api: dict[str, list[str]],
    style: str,
    diff_changed: list[str],
) -> list[str]:
    """Return the highest-priority module paths, capped by style."""
    cap = _COMPACT_MODULE_CAP if style == "compact" else _DETAILED_MODULE_CAP
    changed = frozenset(diff_changed)
    return sorted(public_api, key=lambda p: _rank_module(p, changed), reverse=True)[:cap]


def _hash_module(symbols: list[str]) -> str:
    """Produce a 16-char SHA-256 fingerprint for a module's public symbol list."""
    return hashlib.sha256("|".join(symbols).encode()).hexdigest()[:16]


def _build_understanding_string(summaries: dict[str, str]) -> str:
    """Format per-module summaries into a compact project understanding block."""
    lines = ["Project Understanding:"] + [f"- {mod}: {summary}" for mod, summary in summaries.items()]
    return "\n".join(lines)


def _prompt_for_module(mod: str, content: str, symbols: list[str]) -> str:
    """Build LLM prompt using file content when available, fallback to symbol list."""
    if content:
        return (
            f"Module '{mod}':\n```python\n{content}\n```\n"
            "Describe this module's purpose in one sentence."
        )
    return f"Module '{mod}':\nSymbols: {', '.join(symbols[:20])}\nDescribe this module's purpose in one sentence."


def _partition_modules(
    selected: list[str],
    public_api: dict[str, list[str]],
    cached_hashes: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Split selected modules into fresh (hash changed) and cached (hash matches)."""
    fresh: list[str] = []
    cached: list[str] = []
    for mod in selected:
        if cached_hashes.get(mod) == _hash_module(public_api.get(mod, [])):
            cached.append(mod)
        else:
            fresh.append(mod)
    return fresh, cached


async def _read_module_content(path: Path) -> str:
    """Read truncated file content from disk. Returns empty string on failure."""
    try:
        text: str = await asyncio.to_thread(path.read_text, encoding="utf-8")
        return "\n".join(text.splitlines()[:_MAX_CONTENT_LINES])
    except OSError:
        return ""


async def _summarise_fresh(
    fresh: list[str],
    contents: dict[str, str],
    public_api: dict[str, list[str]],
    model_key: str,
) -> tuple[dict[str, str], int]:
    """Call LLM concurrently for each fresh module. Returns summaries and total tokens."""
    calls = [
        acall_llm(
            model_key,
            README_UNDERSTAND_SYSTEM,
            _prompt_for_module(mod, contents.get(mod, ""), public_api.get(mod, [])),
        )
        for mod in fresh
    ]
    results = await asyncio.gather(*calls)

    summaries: dict[str, str] = {}
    total_tokens = 0
    for mod, (_, raw_text, tokens) in zip(fresh, results, strict=True):
        summaries[mod] = raw_text.strip()
        total_tokens += tokens

    return summaries, total_tokens


async def readme_understand(state: ReadmeState) -> ReadmeUnderstandUpdate:
    """Produce a compact project_understanding string via cheap per-module LLM calls.

    Selects the most important modules (capped by style), reads their content, and
    skips modules whose symbol hash matches the cached value. Short-circuits on
    dry_run or cancellation.
    """
    if state.dry_run or is_cancelled():
        return {}
    if not state.public_api:
        return {}

    cfg = load()
    selected = _select_modules(state.public_api, state.style, state.diff_changed_files)

    base: Path = (
        Path(state.target_path).resolve()
        if state.target_path is not None
        else (state.repo_root or state.repo_path or Path("."))
    )

    raw_contents = await asyncio.gather(*[_read_module_content(base / mod) for mod in selected])
    contents: dict[str, str] = dict(zip(selected, raw_contents, strict=True))

    fresh, cached = _partition_modules(selected, state.public_api, state.module_hashes)
    logger.debug(
        "readme_understand: %d selected, %d fresh, %d cached",
        len(selected),
        len(fresh),
        len(cached),
    )

    fresh_summaries, tokens = await _summarise_fresh(fresh, contents, state.public_api, cfg.defaults.model)

    new_hashes = {
        **state.module_hashes,
        **{mod: _hash_module(state.public_api.get(mod, [])) for mod in fresh},
    }
    new_summaries = {**state.module_summaries, **fresh_summaries}
    ordered = {mod: new_summaries[mod] for mod in selected if mod in new_summaries}
    project_understanding = _build_understanding_string(ordered) if ordered else None

    return {
        "project_understanding": project_understanding,
        "module_summaries": new_summaries,
        "module_hashes": new_hashes,
        "token_actual": tokens,
    }
