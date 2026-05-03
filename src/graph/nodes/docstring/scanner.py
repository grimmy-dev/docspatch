"""scanner node — discovers Python files in the repository."""

from pathlib import Path

from src.schemas.graph_io import ScannerUpdate
from src.schemas.state import DocpatchState
from src.utils.git import get_repo, get_root
from src.utils.ignore import is_ignored, load_ignore
from src.utils.log import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".py"}


def scanner(state: DocpatchState) -> ScannerUpdate:
    """Discover supported files under target_path.

    When from_ref is set, limits to files changed between that ref and HEAD
    (committed range only) plus any untracked files. Without from_ref, scans
    all tracked and untracked files.

    Resolves target_path against git root, not CWD, so CLI relative paths
    cannot escape the repository boundary.
    """
    repo = get_repo(state.repo_path)
    root = get_root(repo)
    target = (Path(state.target_path).resolve() if state.target_path else root).resolve()

    ignore_spec = load_ignore(root)

    if state.from_ref:
        logger.debug("scanner: from_ref=%s, committed range only", state.from_ref)
        rel_files = repo.git.diff("--name-only", state.from_ref, "HEAD", "--", str(target)).splitlines()
    else:
        rel_files = repo.git.ls_files("--cached", str(target)).splitlines()

    untracked = repo.git.ls_files("--others", "--exclude-standard", str(target)).splitlines()

    files: list[Path] = []
    for rel in rel_files + untracked:
        abs_path = root / rel
        if abs_path.suffix not in SUPPORTED_EXTENSIONS:
            continue
        if is_ignored(ignore_spec, root, abs_path):
            logger.debug("scanner: ignored %s", rel)
            continue
        files.append(abs_path)

    logger.debug("scanner: found %d files under %s", len(files), target)
    return {"changed_files": files}
