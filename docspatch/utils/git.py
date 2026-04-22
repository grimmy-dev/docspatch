from pathlib import Path

from git import InvalidGitRepositoryError, Repo


def get_repo(path: str | None = None) -> Repo:
    search_path: Path = Path(path) if path else Path.cwd()
    try:
        return Repo(search_path, search_parent_directories=True)
    except InvalidGitRepositoryError:
        raise RuntimeError(
            f"No git repository found at {search_path}. docspatch requires a git repo."
        )


def is_git_repo(path: str | None = None) -> bool:
    try:
        get_repo(path)
        return True
    except RuntimeError:
        return False


def get_root(repo: Repo | None = None) -> Path:
    r = repo or get_repo()
    if r.working_tree_dir is None:
        raise RuntimeError("Bare repositories are not supported.")
    return Path(r.working_tree_dir)


def get_current_branch(repo: Repo | None = None) -> str:
    r = repo or get_repo()
    try:
        return r.active_branch.name
    except TypeError:
        return r.head.commit.hexsha[:8]  # detached HEAD


def get_changed_files(repo: Repo | None = None) -> list[str]:
    """Return paths of all modified/staged/untracked Python files."""
    r = repo or get_repo()
    root = get_root(r)
    changed: set[str] = set()

    # staged vs HEAD
    if r.head.is_valid():
        for diff in r.index.diff("HEAD"):
            if diff.a_path:
                changed.add(diff.a_path)

    # unstaged (working tree vs index)
    for diff in r.index.diff(None):
        if diff.a_path:
            changed.add(diff.a_path)

    # untracked
    changed.update(r.untracked_files)

    return [str(root / p) for p in changed if p.endswith(".py")]


def get_diff(
    repo: Repo | None = None,
    from_ref: str = "",
    to_ref: str = "HEAD",
) -> str:
    """Return unified diff. from_ref..to_ref range, or working tree vs HEAD."""
    r = repo or get_repo()
    if not r.head.is_valid():
        return ""
    if from_ref:
        return r.git.diff(f"{from_ref}..{to_ref}")
    return r.git.diff(to_ref)


def get_log(
    repo: Repo | None = None,
    n: int = 20,
    from_ref: str = "",
    to_ref: str = "",
) -> list[dict]:
    """Return commits as list of dicts. Optionally scoped to a ref range."""
    r = repo or get_repo()
    if not r.head.is_valid():
        return []
    rev = f"{from_ref}..{to_ref}" if from_ref and to_ref else (to_ref or None)
    commits = []
    for commit in r.iter_commits(rev, max_count=n):
        commits.append(
            {
                "hash": commit.hexsha[:8],
                "message": commit.message.strip(),
                "author": str(commit.author),
                "date": commit.committed_datetime.isoformat(),
            }
        )
    return commits
