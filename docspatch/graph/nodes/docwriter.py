import json

from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console

from docspatch.graph.state import DocpatchState
from docspatch.utils.errors import classify_llm_error
from docspatch.utils.llm import extract_text, extract_tokens, get_llm
from docspatch.utils.ui import spinning, step

_console = Console()

_SYSTEM = {
    "compact": (
        "Documentation expert. Generate concise one-sentence docstrings. "
        "Return ONLY valid JSON array. No markdown fences. No explanation."
    ),
    "detailed": (
        "Documentation expert. Generate multi-section docstrings. "
        "Every docstring MUST have: summary line, blank line, Args section (one line per param with type), "
        "Returns section, Raises section if applicable. "
        "Use Google style. 4-space indent inside sections. "
        "Encode all newlines as \\n in the JSON string value. "
        "Return ONLY valid JSON array. No markdown fences. No explanation."
    ),
}

_STYLE_GUIDE = {
    "compact": (
        "One-sentence summary only. No sections. Args/Returns only if truly non-obvious.\n"
        'Example output: [{"name":"fn","docstring":"Parse config file and return settings dict."}]'
    ),
    "detailed": (
        "Full multi-section docstring. Use \\n for newlines inside the JSON string.\n"
        "Required sections: summary, Args (every param), Returns, Raises (if any).\n"
        "Example output:\n"
        '[{"name":"fn","docstring":'
        '"Fetch user record by ID.\\n\\n'
        "Args:\\n    user_id (int): Primary key of the user.\\n\\n"
        "Returns:\\n    dict: User fields including name and email.\\n\\n"
        'Raises:\\n    ValueError: If user_id is negative."}]'
    ),
}


def _build_prompt(batch: list[dict], style: str) -> str:
    guide = _STYLE_GUIDE.get(style, _STYLE_GUIDE["compact"])
    fn_blocks = "\n---\n".join(f"Name: {fn['name']}\n{fn['body']}" for fn in batch)
    return f"{guide}\n\nFunctions to document:\n---\n{fn_blocks}"


def _build_rerun_prompt(fn: dict, style: str) -> str:
    guide = _STYLE_GUIDE.get(style, _STYLE_GUIDE["compact"])
    prev = fn.get("generated_doc", "")
    feedback = fn.get("feedback", "")
    return (
        f"{guide}\n\n"
        f'Previous docstring: "{prev}"\n'
        f"User feedback: {feedback}\n\n"
        f"Improve the docstring for this function:\n---\nName: {fn['name']}\n{fn['body']}"
    )


def _parse_response(text: str, batch: list[dict]) -> list[dict]:
    text = (
        text.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    try:
        items: list[dict] = json.loads(text)
        by_name = {item["name"]: item["docstring"] for item in items}
    except (json.JSONDecodeError, KeyError, TypeError):
        return []

    return [
        {**fn, "generated_doc": by_name[fn["name"]]}
        for fn in batch
        if fn["name"] in by_name and by_name[fn["name"]]
    ]


def docwriter(state: DocpatchState) -> dict:
    if state.get("dry_run"):
        return {}

    llm = get_llm("model")
    style = state.get("style", "compact")
    system = _SYSTEM.get(style, _SYSTEM["compact"])
    token_actual = state.get("token_actual", 0)

    # Rerun cycle: regenerate docs with user feedback
    if state.get("rerun_docs"):
        rerun_results: list[dict] = []
        for fn in state["rerun_docs"]:
            messages = [
                SystemMessage(content=system),
                HumanMessage(content=_build_rerun_prompt(fn, style)),
            ]
            try:
                with spinning(f"Regenerating  {fn['name']}"):
                    response = llm.invoke(messages)
                parsed = _parse_response(extract_text(response.content), [fn])
                rerun_results.extend(parsed)
                token_actual += extract_tokens(response)
            except Exception as e:
                raise classify_llm_error(e) from e
        tokens_used = token_actual - state.get("token_actual", 0)
        step(
            "Regenerating", f"{len(rerun_results)} docs ready  [{tokens_used:,} tokens]"
        )
        return {
            "generated_docs": rerun_results,
            "rerun_docs": [],
            "token_actual": token_actual,
        }

    # Normal path: process batches
    generated: list[dict] = []
    batch_token_start = token_actual
    total_batches = len(state["batches"])
    for i, batch in enumerate(state["batches"], 1):
        label = (
            f"Generating  ({i}/{total_batches})" if total_batches > 1 else "Generating"
        )
        messages = [
            SystemMessage(content=system),
            HumanMessage(content=_build_prompt(batch, style)),
        ]
        try:
            with spinning(label):
                response = llm.invoke(messages)
            generated.extend(_parse_response(extract_text(response.content), batch))
            token_actual += extract_tokens(response)
        except Exception as e:
            raise classify_llm_error(e) from e

    tokens_used = token_actual - batch_token_start
    step("Generating", f"{len(generated)} docstrings ready  [{tokens_used:,} tokens]")
    return {"generated_docs": generated, "token_actual": token_actual}
