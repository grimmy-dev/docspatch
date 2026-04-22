from langgraph.graph import END, StateGraph

from docspatch.graph.nodes.ast_parser import ast_parser
from docspatch.graph.nodes.preview import preview_all
from docspatch.graph.nodes.readme_writer import readme_writer
from docspatch.graph.nodes.scanner import scanner
from docspatch.graph.nodes.writer import writer
from docspatch.graph.state import DocpatchState


def build() -> object:
    g = StateGraph(DocpatchState)

    g.add_node("scanner", scanner)
    g.add_node("ast_parser", ast_parser)
    g.add_node("readme_writer", readme_writer)
    g.add_node("preview_all", preview_all)
    g.add_node("writer", writer)

    g.set_entry_point("scanner")
    g.add_edge("scanner", "ast_parser")
    g.add_edge("ast_parser", "readme_writer")
    g.add_edge("readme_writer", "preview_all")
    g.add_edge("preview_all", "writer")
    g.add_edge("writer", END)

    return g.compile()
