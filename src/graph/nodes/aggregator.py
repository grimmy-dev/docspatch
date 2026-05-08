"""Aggregator node — combines scout directory summaries into one unified context document.

Step 1: concatenate directory summaries with section headers (no LLM cost).
Step 2: single LLM call to compress, deduplicate, and produce coherent unified summary.
"""

from src.schemas.scout_io import FileSummary
from src.utils.llm.caller import acall_llm, is_cancelled
from src.utils.log import get_logger

__all__ = ["aggregator_node"]

logger = get_logger(__name__)

_AGGREGATOR_SYSTEM = (
    "You are a technical writer. You will receive a structured summary of a codebase "
    "organised by directory. Compress it into a single coherent description of what the "
    "codebase does, what its main components are, and how they relate. Remove redundancy. "
    "Write in plain prose. Be specific — no generic statements."
)


def _concat_grouped(grouped: dict[str, list[FileSummary]]) -> str:
    """Concatenate directory summaries into a structured text document."""
    sections: list[str] = []
    for dir_key, summaries in grouped.items():
        lines = [f"## {dir_key}", ""]
        for s in summaries:
            symbols = ", ".join(s["key_symbols"]) if s["key_symbols"] else ""
            line = f"- {s['path']}: {s['summary']}"
            if symbols:
                line += f" [{symbols}]"
            lines.append(line)
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


async def aggregator_node(
    *,
    grouped: dict[str, list[FileSummary]],
    model_key: str,
    existing_unified: str | None = None,
) -> str:
    """Produce a unified context string from scout's directory-grouped summaries.

    existing_unified: prior aggregated context; prepended to prompt so the LLM
    can merge new summaries with what was already known.
    Returns empty string when grouped is empty or cancellation is requested.
    """
    if is_cancelled() or not grouped:
        return ""

    concat = _concat_grouped(grouped)
    if existing_unified:
        prompt = f"Existing unified context:\n{existing_unified}\n\nNew file summaries to incorporate:\n{concat}"
    else:
        prompt = concat
    logger.debug("aggregator_node dirs=%d prompt_len=%d", len(grouped), len(prompt))

    _, raw_text, tokens = await acall_llm(model_key, _AGGREGATOR_SYSTEM, prompt)
    logger.debug("aggregator_node tokens=%d", tokens)
    return raw_text.strip()
