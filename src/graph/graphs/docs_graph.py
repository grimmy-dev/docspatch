"""Build the full dp docs LangGraph pipeline."""

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.graph.graphs.shared import add_docwrite_nodes, add_write_cycle_nodes
from src.schemas.graph_io import Checkpointer
from src.schemas.state import DocpatchState


def has_changed_files(state: DocpatchState) -> Literal["continue", "no_changed_files"]:
    """Determines if there are any changed files in the current state.

    Args:
        state: The current DocpatchState.

    Returns:
        "continue" if changed files exist, otherwise "no_changed_files"."""
    return "continue" if state.changed_files else "no_changed_files"


def has_significant(state: DocpatchState) -> Literal["continue", "nothing_significant"]:
    """Checks if significant functions were identified in the current state.

    Args:
        state: The current DocpatchState.

    Returns:
        "continue" if significant functions exist, otherwise "nothing_significant"."""
    return "continue" if state.significant_functions else "nothing_significant"


def build(
    checkpointer: Checkpointer | None = None,
) -> CompiledStateGraph[DocpatchState]:
    """Assembles and compiles the full Docpatch state graph pipeline.

    Args:
        checkpointer: An optional Checkpointer for graph state persistence.

    Returns:
        A compiled state graph for the Docpatch pipeline."""
    from src.graph.nodes.hash_check import file_hash_check, function_hash_check
    from src.graph.nodes.libcst_parser import libcst_parser
    from src.graph.nodes.scanner import scanner
    from src.graph.nodes.significance import significance
    from src.graph.nodes.size_check import size_check

    builder = StateGraph(DocpatchState)

    # Core pipeline nodes
    builder.add_node("scanner", scanner)
    builder.add_node("file_hash_check", file_hash_check)
    builder.add_node("libcst_parser", libcst_parser)
    builder.add_node("function_hash_check", function_hash_check)
    builder.add_node("significance", significance)
    builder.add_node("size_check", size_check)

    # Subgraph sections (returns entry/exit node names)
    docwrite_entry, docwrite_exit = add_docwrite_nodes(builder)
    write_entry, _ = add_write_cycle_nodes(builder)

    # Static edges
    builder.add_edge(START, "scanner")
    builder.add_edge("scanner", "file_hash_check")

    # Conditional: file hash check
    builder.add_conditional_edges(
        "file_hash_check",
        has_changed_files,
        {"continue": "libcst_parser", "no_changed_files": END},
    )

    builder.add_edge("libcst_parser", "function_hash_check")
    builder.add_edge("function_hash_check", "significance")

    # Conditional: significance
    builder.add_conditional_edges(
        "significance",
        has_significant,
        {"continue": "size_check", "nothing_significant": END},
    )

    builder.add_edge("size_check", docwrite_entry)
    builder.add_edge(docwrite_exit, write_entry)

    return builder.compile(checkpointer=checkpointer)
