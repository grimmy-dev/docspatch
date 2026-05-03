"""Build the dp readme LangGraph pipeline."""

from langgraph.graph import END, START, StateGraph

from src.schemas.readme_state import CompiledReadmeGraph, ReadmeState
from src.utils.checkpointer import get_memory_saver


def _after_diff_filter(state: ReadmeState) -> str:
    return END if state.up_to_date else "readme_llm"


def build() -> CompiledReadmeGraph:
    """Assemble and compile the readme pipeline. Always uses MemorySaver — never SqliteSaver."""
    from src.graph.nodes.preview import readme_preview_all
    from src.graph.nodes.readme.context import readme_context
    from src.graph.nodes.readme.diff_filter import readme_diff_filter
    from src.graph.nodes.readme.generate import readme_llm
    from src.graph.nodes.readme.writer import readme_writer

    builder: StateGraph[ReadmeState] = StateGraph(ReadmeState)

    builder.add_node("readme_context", readme_context)
    builder.add_node("readme_diff_filter", readme_diff_filter)
    builder.add_node("readme_llm", readme_llm)
    builder.add_node("readme_preview", readme_preview_all)
    builder.add_node("readme_writer", readme_writer)

    builder.add_edge(START, "readme_context")
    builder.add_edge("readme_context", "readme_diff_filter")
    builder.add_conditional_edges("readme_diff_filter", _after_diff_filter, ["readme_llm", END])
    builder.add_edge("readme_llm", "readme_preview")
    builder.add_edge("readme_preview", "readme_writer")
    builder.add_edge("readme_writer", END)

    return builder.compile(checkpointer=get_memory_saver())
