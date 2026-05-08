"""clg_scout LangGraph node — wraps scout_node for the changelog pipeline."""

from pathlib import Path

from src.graph.nodes.scout import scout_node
from src.schemas.changelog_io import ChangelogScoutUpdate
from src.schemas.changelog_state import ChangelogState
from src.schemas.scout_io import ScoutOutput
from src.utils.config import load
from src.utils.llm.caller import is_cancelled
from src.utils.log import get_logger

__all__ = ["clg_scout"]

logger = get_logger(__name__)


async def clg_scout(state: ChangelogState) -> ChangelogScoutUpdate:
    """Run scout analysis for the changelog pipeline.

    Initial commit: readme mode, scans all Python files in the repo.
    Incremental: clg mode, scopes to state.changed_files.
    """
    if state.dry_run or is_cancelled():
        return {}

    cfg = load()
    root = state.repo_path or Path(".")

    if state.is_initial_commit:
        output: ScoutOutput = await scout_node(
            target_path=root,
            repo_root=root,
            mode="readme",
            model_key=cfg.defaults.scout_model,
        )
    else:
        output = await scout_node(
            target_path=root,
            repo_root=root,
            mode="clg",
            changed_files=state.changed_files,
            model_key=cfg.defaults.scout_model,
        )

    logger.debug(
        "clg_scout: summaries=%d cache_hits=%d tokens=%d",
        len(output["summaries"]),
        output["cache_hits"],
        output["tokens_used"],
    )
    return {"scout_output": output, "token_actual": output["tokens_used"]}
