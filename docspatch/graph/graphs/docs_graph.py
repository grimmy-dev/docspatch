from langgraph.graph import END, StateGraph

from docspatch.graph.nodes.ast_parser import ast_parser
from docspatch.graph.nodes.batcher import batcher
from docspatch.graph.nodes.docwriter import docwriter
from docspatch.graph.nodes.hash_check import file_hash_check, function_hash_check
from docspatch.graph.nodes.preview import has_rerun, preview_all
from docspatch.graph.nodes.scanner import scanner
from docspatch.graph.nodes.significance import significance
from docspatch.graph.nodes.size_check import size_check
from docspatch.graph.nodes.writer import cache_update, writer
from docspatch.graph.state import DocpatchState
from docspatch.utils.ui import info


def _has_significant(state: DocpatchState) -> str:
    """
    Return 'exit' if no meaningful changes were found, otherwise 'continue'.
    """
    if not state["parsed_functions"]:
        info("No meaningful changes — only whitespace or comments.")
        return "exit"
    return "continue"


def _has_changed_files(state: DocpatchState) -> str:
    """Return 'exit' if no files have changed, otherwise 'continue'."""
    if not state["changed_files"]:
        info("Nothing changed since last run.")
        return "exit"
    return "continue"


def build() -> object:
    """Build the state graph for the docpatcher."""
    g = StateGraph(DocpatchState)

    g.add_node("scanner", scanner)
    g.add_node("file_hash_check", file_hash_check)
    g.add_node("ast_parser", ast_parser)
    g.add_node("function_hash_check", function_hash_check)
    g.add_node("significance", significance)
    g.add_node("size_check", size_check)
    g.add_node("batcher", batcher)
    g.add_node("docwriter", docwriter)
    g.add_node("preview_all", preview_all)
    g.add_node("writer", writer)
    g.add_node("cache_update", cache_update)

    g.set_entry_point("scanner")
    g.add_edge("scanner", "file_hash_check")
    g.add_conditional_edges(
        "file_hash_check", _has_changed_files, {"continue": "ast_parser", "exit": END}
    )
    g.add_edge("ast_parser", "function_hash_check")
    g.add_edge("function_hash_check", "significance")
    g.add_conditional_edges(
        "significance", _has_significant, {"continue": "size_check", "exit": END}
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
