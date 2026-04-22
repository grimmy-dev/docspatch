from langchain_core.messages import HumanMessage, SystemMessage

from docspatch.graph.state import DocpatchState
from docspatch.utils.errors import classify_llm_error
from docspatch.utils.git import get_repo, get_root
from docspatch.utils.llm import get_llm
from docspatch.utils.ui import spinning

_SYSTEM = (
    "You are a technical writer. Generate clear, developer-focused README files. "
    "Use Markdown. Be concise — no fluff, no motivational language."
)

_STYLE_GUIDE = {
    "compact": "Short sections: what it is, install, usage, config. No examples unless essential.",
    "detailed": "Full README: description, features, install, usage with examples, config reference, contributing.",
}


def _collect_context(state: DocpatchState) -> str:
    repo = get_repo()
    root = get_root(repo)
    style = state.get("style", "compact")
    guide = _STYLE_GUIDE.get(style, _STYLE_GUIDE["compact"])

    functions = state.get("parsed_functions", [])
    fn_summary = "\n".join(
        f"- {fn['file'].replace(str(root) + '/', '')}::{fn['name']}  {fn.get('existing_doc', '').split(chr(10))[0]}"
        for fn in functions[:40]  # cap context
    )

    return (
        f"Project root: {root}\n"
        f"Style: {guide}\n\n"
        f"Key functions:\n{fn_summary or '(none parsed)'}\n\n"
        "Generate a README.md for this project."
    )


def readme_writer(state: DocpatchState) -> dict:
    if state.get("dry_run"):
        return {}

    llm = get_llm("model")
    messages = [
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=_collect_context(state)),
    ]
    try:
        with spinning("Writing README"):
            response = llm.invoke(messages)
    except Exception as e:
        raise classify_llm_error(e) from e

    token_actual = state.get("token_actual", 0)
    meta = getattr(response, "usage_metadata", None)
    if meta:
        token_actual += meta.get("total_tokens", 0) or (
            meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
        )

    # Store in generated_docs as a single entry for preview node to handle
    readme_doc = {
        "name": "README.md",
        "file": state.get("target_path", "README.md"),
        "generated_doc": response.content,
    }
    return {"generated_docs": [readme_doc], "token_actual": token_actual}
