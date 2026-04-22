from docspatch.graph.state import DocpatchState
from docspatch.utils.ui import step


def significance(state: DocpatchState) -> dict:
    """Keep only functions flagged significant by function_hash_check."""
    significant = [fn for fn in state["parsed_functions"] if fn.get("is_significant")]
    skipped = len(state["parsed_functions"]) - len(significant)
    detail = f"{len(significant)} meaningful"
    if skipped:
        detail += f", {skipped} unchanged"
    step("Significance", detail)
    return {"parsed_functions": significant}


def has_significant_functions(state: DocpatchState) -> str:
    """Routing condition: 'continue' or 'exit'."""
    return "continue" if state["parsed_functions"] else "exit"
