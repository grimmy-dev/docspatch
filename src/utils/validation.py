"""State validation — runs before any pipeline work starts."""

from pathlib import Path

__all__ = ["validate_state"]

from git.exc import GitCommandError

from src.schemas.state import DocpatchState
from src.utils.git import get_repo, get_root


def validate_state(state: DocpatchState) -> None:
    """Check all preconditions before a pipeline run; raises ValueError on failure.

    Resolves paths against git root (not CWD) so relative CLI inputs
    cannot escape the repository boundary.
    """
    repo = get_repo()
    root = get_root(repo)

    if state.target_path is not None:
        target = Path(state.target_path).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Target path '{target}' is outside git root '{root}'") from exc
        if not target.exists():
            raise ValueError(f"Target path does not exist: {target}")

    if state.from_ref is not None:
        try:
            repo.git.rev_parse(state.from_ref)
        except GitCommandError as exc:
            raise ValueError(f"Invalid git ref: '{state.from_ref}'") from exc

    if state.style not in ("compact", "detailed"):
        raise ValueError(f"Style must be 'compact' or 'detailed', got: '{state.style}'")

    if state.output_path is not None and state.output_path.is_dir():
        raise ValueError(f"output_path must be a file, not a directory: {state.output_path}")
