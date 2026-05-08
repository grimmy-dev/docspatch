"""readme_scout LangGraph node — wraps scout_node for the README pipeline."""

from pathlib import Path

from src.graph.nodes.scout import scout_node
from src.schemas.readme_io import ReadmeScoutUpdate
from src.schemas.readme_state import ReadmeState
from src.utils.config import load
from src.utils.llm.caller import is_cancelled
from src.utils.log import get_logger
from src.utils.persistent_cache import get_scope_dir

__all__ = ["readme_scout"]

logger = get_logger(__name__)

_CACHE_SUBDIR = Path(".docspatch") / "cache"


async def readme_scout(state: ReadmeState) -> ReadmeScoutUpdate:
    """Run scout analysis over target_path and store ScoutOutput in state.

    Full scan when no diff_changed_files; scoped to changed files when incremental.
    Persistent cache used when repo_root is available.
    """
    if state.dry_run or is_cancelled():
        return {}

    cfg = load()
    target = Path(state.target_path).resolve() if state.target_path is not None else (state.repo_root or state.repo_path or Path("."))
    root = state.repo_root or state.repo_path or target

    changed_files: list[str] | None = state.diff_changed_files if state.diff_changed_files else None

    scope_dir: Path | None = None
    if state.repo_root is not None:
        cache_root = root / _CACHE_SUBDIR
        scope_dir = get_scope_dir(cache_root, target, root)

    output = await scout_node(
        target_path=target,
        repo_root=root,
        mode="readme",
        changed_files=changed_files,
        existing_doc=state.existing_readme,
        model_key=cfg.defaults.model,
        scope_dir=scope_dir,
    )

    logger.debug(
        "readme_scout: summaries=%d cache_hits=%d tokens=%d",
        len(output["summaries"]),
        output["cache_hits"],
        output["tokens_used"],
    )
    return {"scout_output": output, "token_actual": output["tokens_used"]}
