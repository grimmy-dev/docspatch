"""Interrupt-based preview nodes for docs and readme pipelines."""

from langgraph.types import interrupt

from src.schemas.graph_io import PreviewUpdate, ReviewInterrupt, ReviewSessionResult
from src.schemas.readme_io import ReadmePreviewUpdate, ReadmeReviewInterrupt
from src.schemas.readme_state import ReadmeState
from src.schemas.state import DocpatchState


def docs_preview_all(state: DocpatchState) -> PreviewUpdate:
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


def readme_preview_all(state: ReadmeState) -> ReadmePreviewUpdate:
    """Interrupt the graph so the CLI can present the generated README for review."""
    if not state.generated_readme:
        return {"accepted_readme": None}

    result: str | None = interrupt(ReadmeReviewInterrupt(type="readme_review", content=state.generated_readme))
    return {"accepted_readme": result}
