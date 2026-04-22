from docspatch.graph.state import DocpatchState

MAX_PER_BATCH = 10


def batcher(state: DocpatchState) -> dict:
    """Group functions into batches by file, capped at MAX_PER_BATCH each."""
    by_file: dict[str, list[dict]] = {}
    for fn in state["parsed_functions"]:
        by_file.setdefault(fn["file"], []).append(fn)

    batches: list[list[dict]] = []
    for file_fns in by_file.values():
        for i in range(0, len(file_fns), MAX_PER_BATCH):
            batches.append(file_fns[i : i + MAX_PER_BATCH])

    return {"batches": batches}
