import json

from langchain_core.messages import HumanMessage, SystemMessage

from docspatch.graph.state import DocpatchState
from docspatch.utils.errors import classify_llm_error
from docspatch.utils.llm import get_llm
from docspatch.utils.ui import spinning, step

_SYSTEM = (
    "You are a Python documentation expert. "
    "Generate accurate, concise docstrings. "
    "Return ONLY valid JSON — no markdown, no explanation."
)

_STYLE_GUIDE = {
    "compact": "One-sentence summary. Add Args/Returns only when non-obvious.",
    "detailed": "Full summary. Document all Args, Returns, and Raises. Add examples if helpful.",
}


def _extract_text(content: str | list) -> str:
    if isinstance(content, str):
        return content
    return " ".join(
        block.get("text", "") if isinstance(block, dict) else str(block)
        for block in content
    )


def _build_prompt(batch: list[dict], style: str) -> str:
    guide = _STYLE_GUIDE.get(style, _STYLE_GUIDE["compact"])
    fn_blocks = "\n---\n".join(
        f"Name: {fn['name']}\n{fn['body']}" for fn in batch
    )
    return (
        f"Style: {guide}\n\n"
        "Return a JSON array, one entry per function in the same order:\n"
        '[{"name": "fn_name", "docstring": "content without triple quotes"}, ...]\n\n'
        f"Functions:\n---\n{fn_blocks}"
    )


def _build_rerun_prompt(fn: dict, style: str) -> str:
    guide = _STYLE_GUIDE.get(style, _STYLE_GUIDE["compact"])
    prev = fn.get("generated_doc", "")
    feedback = fn.get("feedback", "")
    return (
        f"Style: {guide}\n\n"
        f"Previous docstring: \"{prev}\"\n"
        f"User feedback: {feedback}\n\n"
        "Return a JSON array with one entry:\n"
        '[{"name": "fn_name", "docstring": "improved content without triple quotes"}]\n\n'
        f"Function:\n---\nName: {fn['name']}\n{fn['body']}"
    )


def _parse_response(text: str, batch: list[dict]) -> list[dict]:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
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


def _extract_tokens(response) -> int:
    meta = getattr(response, "usage_metadata", None)
    if not meta:
        return 0
    return meta.get("total_tokens", 0) or (
        meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
    )


def docwriter(state: DocpatchState) -> dict:
    if state.get("dry_run"):
        return {}

    llm = get_llm("model")
    style = state.get("style", "compact")
    token_actual = state.get("token_actual", 0)

    # Rerun cycle: regenerate skipped docs with user feedback
    if state.get("rerun_docs"):
        rerun_results: list[dict] = []
        for fn in state["rerun_docs"]:
            messages = [
                SystemMessage(content=_SYSTEM),
                HumanMessage(content=_build_rerun_prompt(fn, style)),
            ]
            try:
                with spinning(f"Regenerating  {fn['name']}"):
                    response = llm.invoke(messages)
                parsed = _parse_response(_extract_text(response.content), [fn])
                rerun_results.extend(parsed)
                token_actual += _extract_tokens(response)
            except Exception as e:
                raise classify_llm_error(e) from e
        step("Regenerating", f"{len(rerun_results)} docs ready")
        return {"generated_docs": rerun_results, "rerun_docs": [], "token_actual": token_actual}

    # Normal path: process batches
    generated: list[dict] = []
    total_batches = len(state["batches"])
    for i, batch in enumerate(state["batches"], 1):
        label = f"Generating  ({i}/{total_batches})" if total_batches > 1 else "Generating"
        messages = [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=_build_prompt(batch, style)),
        ]
        try:
            with spinning(label):
                response = llm.invoke(messages)
            generated.extend(_parse_response(_extract_text(response.content), batch))
            token_actual += _extract_tokens(response)
        except Exception as e:
            raise classify_llm_error(e) from e

    step("Generating", f"{len(generated)} docstrings ready")
    return {"generated_docs": generated, "token_actual": token_actual}
