from rich.console import Console
from rich.panel import Panel
from langchain_core.messages import HumanMessage, SystemMessage

from docspatch.graph.state import DocpatchState
from docspatch.utils.errors import classify_llm_error
from docspatch.utils.llm import extract_text, extract_tokens, get_llm
from docspatch.utils.ui import spinning, step

_console = Console()

_SYSTEM = (
    "Senior engineer doing code review. "
    "Direct and specific. Flag real issues only. No style nitpicks."
)

_STYLE_GUIDE = {
    "compact": "One bullet per issue. Format: `name`: issue.",
    "detailed": "Group by severity: error / warning / suggestion. Explain why each matters.",
}


def _build_prompt(functions: list[dict], style: str) -> str:
    guide = _STYLE_GUIDE.get(style, _STYLE_GUIDE["compact"])
    fn_blocks = "\n---\n".join(
        f"# {fn['file']} — {fn['name']}\n{fn['body']}" for fn in functions
    )
    return f"Review for correctness, edge cases, robustness.\n{guide}\n\n{fn_blocks}"


def reviewer(state: DocpatchState) -> dict:
    if state.get("dry_run"):
        return {}

    llm = get_llm("review_model")
    style = state.get("style", "compact")
    functions = state.get("parsed_functions", [])

    if not functions:
        return {"feedback": {}}

    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=_build_prompt(functions, style)),
    ]
    try:
        with spinning("Reviewing"):
            response = llm.invoke(messages)
    except Exception as e:
        raise classify_llm_error(e) from e

    token_actual = state.get("token_actual", 0) + extract_tokens(response)
    review_text = extract_text(response.content)
    _console.print(Panel(review_text, title="Code Review", border_style="cyan"))
    step("Review", "done")
    return {"feedback": {"__review__": review_text}, "token_actual": token_actual}
