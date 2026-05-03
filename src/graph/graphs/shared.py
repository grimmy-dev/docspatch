"""Shared graph construction logic for fan-out and review cycles."""

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from src.schemas.state import DocpatchState


def fan_out_batches(state: DocpatchState) -> list[Send]:
    """Maps each function batch to a parallel docwriter node.

    Args:
        state (DocpatchState): The current state of the docpatch process.

    Returns:
        list[Send]: A list of Send objects, each targeting a "docwriter_single" node with an updated state."""
    return [
        Send(
            "docwriter_single",
            state.model_copy(update={"current_batch": batch}),
        )
        for batch in state.batches
    ]


def add_docwrite_nodes(g: StateGraph[DocpatchState]) -> tuple[str, str]:
    """Attaches the parallel batch processing nodes to the graph.

    Args:
        g (StateGraph[DocpatchState]): The state graph to which nodes will be added.

    Returns:
        tuple[str, str]: A tuple containing the entry and exit node names for the added subgraph."""
    from src.graph.nodes.docstring.batcher import batcher
    from src.graph.nodes.docstring.docwriter import collect_batches, docwriter_single

    g.add_node("batcher", batcher)
    g.add_node("docwriter_single", docwriter_single)
    g.add_node("collect_batches", collect_batches)

    g.add_conditional_edges("batcher", fan_out_batches, ["docwriter_single"])
    g.add_edge("docwriter_single", "collect_batches")

    return "batcher", "collect_batches"


def add_write_cycle_nodes(g: StateGraph[DocpatchState]) -> tuple[str, str]:
    """Attaches the preview, write, and revision loop nodes to the graph.

    Args:
        g (StateGraph[DocpatchState]): The state graph to which nodes will be added.

    Returns:
        tuple[str, str]: A tuple containing the entry and exit node names for the added subgraph."""
    from src.graph.nodes.docstring.docwriter import docwriter_rerun
    from src.graph.nodes.docstring.writer import cache_update, writer
    from src.graph.nodes.preview import docs_preview_all, has_rerun

    g.add_node("docs_preview_all", docs_preview_all)
    g.add_node("writer", writer)
    g.add_node("cache_update", cache_update)
    g.add_node("docwriter_rerun", docwriter_rerun)

    g.add_edge("docs_preview_all", "writer")
    g.add_edge("writer", "cache_update")
    g.add_conditional_edges("cache_update", has_rerun, {"rerun": "docwriter_rerun", "done": END})
    g.add_edge("docwriter_rerun", "docs_preview_all")

    return "docs_preview_all", "cache_update"
