from langgraph.graph import END, StateGraph

from docspatch.graph.nodes.ast_parser import ast_parser
from docspatch.graph.nodes.hash_check import file_hash_check
from docspatch.graph.nodes.reviewer import reviewer
from docspatch.graph.nodes.scanner import scanner
from docspatch.graph.state import DocpatchState


def _has_changed_files(state: DocpatchState) -> str:
    return "continue" if state["changed_files"] else "exit"


def build() -> object:
    g = StateGraph(DocpatchState)

    g.add_node("scanner", scanner)
    g.add_node("file_hash_check", file_hash_check)
    g.add_node("ast_parser", ast_parser)
    g.add_node("reviewer", reviewer)

    g.set_entry_point("scanner")
    g.add_edge("scanner", "file_hash_check")
    g.add_conditional_edges("file_hash_check", _has_changed_files, {"continue": "ast_parser", "exit": END})
    g.add_edge("ast_parser", "reviewer")
    g.add_edge("reviewer", END)

    return g.compile()
