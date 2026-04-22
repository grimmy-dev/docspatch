from langgraph.graph import END, StateGraph
from rich.console import Console

from docspatch.graph.nodes.ast_parser import ast_parser

console = Console()
from docspatch.graph.nodes.batcher import batcher
from docspatch.graph.nodes.docwriter import docwriter
from docspatch.graph.nodes.hash_check import file_hash_check, function_hash_check
from docspatch.graph.nodes.preview import collect_feedback, has_skipped, preview_all, prompt_rerun
from docspatch.graph.nodes.scanner import scanner
from docspatch.graph.nodes.significance import significance
from docspatch.graph.nodes.size_check import size_check
from docspatch.graph.nodes.writer import cache_update, writer
from docspatch.graph.state import DocpatchState


def _has_significant(state: DocpatchState) -> str:
    if not state["parsed_functions"]:
        console.print("  [dim]No meaningful changes — only whitespace or comments.[/dim]")
        return "exit"
    return "continue"


def _has_changed_files(state: DocpatchState) -> str:
    if not state["changed_files"]:
        console.print("  [dim]Nothing changed since last run.[/dim]")
        return "exit"
    return "continue"


def build() -> object:
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
    g.add_node("prompt_rerun", prompt_rerun)
    g.add_node("collect_feedback", collect_feedback)

    g.set_entry_point("scanner")
    g.add_edge("scanner", "file_hash_check")
    g.add_conditional_edges("file_hash_check", _has_changed_files, {"continue": "ast_parser", "exit": END})
    g.add_edge("ast_parser", "function_hash_check")
    g.add_edge("function_hash_check", "significance")
    g.add_conditional_edges("significance", _has_significant, {"continue": "size_check", "exit": END})
    g.add_edge("size_check", "batcher")
    g.add_edge("batcher", "docwriter")
    g.add_edge("docwriter", "preview_all")
    g.add_edge("preview_all", "writer")
    g.add_edge("writer", "cache_update")
    g.add_edge("cache_update", "prompt_rerun")
    g.add_conditional_edges("prompt_rerun", has_skipped, {"rerun": "collect_feedback", "done": END})
    g.add_edge("collect_feedback", "docwriter")

    return g.compile()
