from pathlib import Path

from docspatch.graph.state import DocpatchState
from docspatch.utils.git import get_repo, get_root
from docspatch.utils.ui import step


def scanner(state: DocpatchState) -> dict:
    """Walk repo files, respect .gitignore, filter to Python only."""
    repo = get_repo()
    root = get_root(repo)
    target = Path(state["target_path"]).resolve() if state.get("target_path") else None

    # git ls-files respects .gitignore natively
    tracked = repo.git.ls_files().splitlines()
    untracked = repo.git.ls_files("--others", "--exclude-standard").splitlines()

    py_files: list[str] = []
    for rel_path in sorted(set(tracked) | set(untracked)):
        if not rel_path.endswith(".py"):
            continue
        abs_path = (root / rel_path).resolve()
        if target:
            if target.is_file():
                if abs_path != target:
                    continue
            else:
                try:
                    abs_path.relative_to(target)
                except ValueError:
                    continue
        py_files.append(str(abs_path))

    step("Scanning", f"{len(py_files)} Python files")
    return {"files": py_files}
