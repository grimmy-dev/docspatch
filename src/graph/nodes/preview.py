"""preview node — interrupt-based docstring review session."""

from langgraph.types import interrupt

from src.schemas.graph_io import PreviewUpdate, ReviewInterrupt, ReviewSessionResult
from src.schemas.state import DocpatchState


def preview_all(state: DocpatchState) -> PreviewUpdate:
    """Interrupt the graph so the CLI can run the interactive review session."""
    if not state.generated_docs:
        return {"accepted_docs": {}, "rerun_docs": [], "feedback": {}}

    if state.rerun_docs:
        docs_to_review = {fid: state.generated_docs[fid] for fid in state.rerun_docs if fid in state.generated_docs}
    else:
        docs_to_review = state.generated_docs

    if not docs_to_review:
        return {"accepted_docs": {}, "rerun_docs": [], "feedback": {}}

    result: ReviewSessionResult = interrupt(ReviewInterrupt(type="review", docs=docs_to_review))

    return {
        "accepted_docs": result["accepted"],
        "rerun_docs": result["rerun"],
        "feedback": result["feedback"],
    }


def has_rerun(state: DocpatchState) -> str:
    """Conditional edge: loop back to rerun node when rerun_docs is non-empty."""
    return "rerun" if state.rerun_docs else "done"
