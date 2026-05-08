"""Build the dp clg LangGraph pipeline."""

from langgraph.graph import END, START, StateGraph

from src.schemas.changelog_state import ChangelogState, CompiledChangelogGraph
from src.utils.checkpointer import get_memory_saver


def _after_context(state: ChangelogState) -> str:
    return END if state.nothing_to_document else "clg_scout"


def build() -> CompiledChangelogGraph:
    """Assemble and compile the changelog pipeline. Always uses MemorySaver."""
    from src.graph.nodes.changelog.aggregator import clg_aggregator
    from src.graph.nodes.changelog.context import clg_context
    from src.graph.nodes.changelog.generate import clg_llm
    from src.graph.nodes.changelog.scout import clg_scout
    from src.graph.nodes.changelog.writer import clg_writer
    from src.graph.nodes.preview import clg_preview_all

    builder: StateGraph[ChangelogState] = StateGraph(ChangelogState)

    builder.add_node("clg_context", clg_context)
    builder.add_node("clg_scout", clg_scout)
    builder.add_node("clg_aggregator", clg_aggregator)
    builder.add_node("clg_llm", clg_llm)
    builder.add_node("clg_preview", clg_preview_all)
    builder.add_node("clg_writer", clg_writer)

    builder.add_edge(START, "clg_context")
    builder.add_conditional_edges("clg_context", _after_context, ["clg_scout", END])
    builder.add_edge("clg_scout", "clg_aggregator")
    builder.add_edge("clg_aggregator", "clg_llm")
    builder.add_edge("clg_llm", "clg_preview")
    builder.add_edge("clg_preview", "clg_writer")
    builder.add_edge("clg_writer", END)

    return builder.compile(checkpointer=get_memory_saver())
