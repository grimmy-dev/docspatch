import hashlib

from docspatch.graph.state import DocpatchState
from docspatch.utils import cache
from docspatch.utils.ui import step


def _hash_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def file_hash_check(state: DocpatchState) -> dict:
    """Skip files unchanged since last docspatch run."""
    changed: list[str] = []
    for path in state["files"]:
        try:
            current = _hash_file(path)
        except OSError:
            continue
        if current != cache.get_file_hash(path):
            changed.append(path)
    unchanged = len(state["files"]) - len(changed)
    step("Hash check", f"{len(changed)} changed, {unchanged} unchanged")
    return {"changed_files": changed}


def function_hash_check(state: DocpatchState) -> dict:
    """Mark functions unchanged since last run — runs after ast_parser."""
    functions = []
    for fn in state["parsed_functions"]:
        cached_hash = cache.get_function_hash(fn["file"], fn["name"])
        functions.append({**fn, "is_significant": cached_hash != fn["body_hash"]})
    return {"parsed_functions": functions}
