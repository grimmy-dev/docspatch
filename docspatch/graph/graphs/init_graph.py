from langgraph.graph import END, StateGraph

from docspatch.graph.nodes.ast_parser import ast_parser
from docspatch.graph.nodes.batcher import batcher
from docspatch.graph.nodes.docwriter import docwriter
from docspatch.graph.nodes.preview import has_rerun, preview_all
from docspatch.graph.nodes.scanner import scanner
from docspatch.graph.nodes.size_check import size_check
from docspatch.graph.nodes.writer import cache_update, writer
from docspatch.graph.state import DocpatchState


def _smart_filter(state: DocpatchState) -> dict:
    """For init: only process undocumented functions."""
    undocumented = [
        {**fn, "is_significant": True}
        for fn in state["parsed_functions"]
        if not fn.get("existing_doc")
    ]
    return {"parsed_functions": undocumented, "changed_files": state["files"]}


def _has_functions(state: DocpatchState) -> str:
    return "continue" if state["parsed_functions"] else "exit"


def build() -> object:
    g = StateGraph(DocpatchState)

    g.add_node("scanner", scanner)
    g.add_node("ast_parser", ast_parser)
    g.add_node("smart_filter", _smart_filter)
    g.add_node("size_check", size_check)
    g.add_node("batcher", batcher)
    g.add_node("docwriter", docwriter)
    g.add_node("preview_all", preview_all)
    g.add_node("writer", writer)
    g.add_node("cache_update", cache_update)

    g.set_entry_point("scanner")
    g.add_edge("scanner", "ast_parser")
    g.add_edge("ast_parser", "smart_filter")
    g.add_conditional_edges(
        "smart_filter", _has_functions, {"continue": "size_check", "exit": END}
    )
    g.add_edge("size_check", "batcher")
    g.add_edge("batcher", "docwriter")
    g.add_edge("docwriter", "preview_all")
    g.add_edge("preview_all", "writer")
    g.add_edge("writer", "cache_update")
    g.add_conditional_edges(
        "cache_update", has_rerun, {"rerun": "docwriter", "done": END}
    )

    return g.compile()
