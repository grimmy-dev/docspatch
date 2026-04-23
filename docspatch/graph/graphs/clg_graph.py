from langgraph.graph import END, StateGraph

from docspatch.graph.nodes.clg_writer import clg_writer
from docspatch.graph.nodes.preview import preview_all
from docspatch.graph.nodes.writer import writer
from docspatch.graph.state import DocpatchState


def build() -> object:
    """Builds and compiles a StateGraph for document processing."""
    g = StateGraph(DocpatchState)

    g.add_node("clg_writer", clg_writer)
    g.add_node("preview_all", preview_all)
    g.add_node("writer", writer)

    g.set_entry_point("clg_writer")
    g.add_edge("clg_writer", "preview_all")
    g.add_edge("preview_all", "writer")
    g.add_edge("writer", END)

    return g.compile()
