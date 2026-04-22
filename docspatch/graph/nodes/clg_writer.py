from langchain_core.messages import HumanMessage, SystemMessage

from docspatch.graph.state import DocpatchState
from docspatch.utils.errors import classify_llm_error
from docspatch.utils.git import get_diff, get_log, get_repo
from docspatch.utils.llm import get_llm
from docspatch.utils.ui import spinning

_SYSTEM = (
    "You are a technical writer generating changelogs. "
    "Use Keep a Changelog format. Group by: Added, Changed, Fixed, Removed. "
    "Be specific — reference function names and modules. No vague entries."
)

_STYLE_GUIDE = {
    "compact": "One bullet per logical change. Skip minor refactors.",
    "detailed": "Full entries with context. Include breaking changes section if any.",
}


def clg_writer(state: DocpatchState) -> dict:
    if state.get("dry_run"):
        return {}

    repo = get_repo()
    from_ref = state.get("from_ref", "")
    to_ref = state.get("to_ref", "") or "HEAD"
    diff = get_diff(repo, from_ref=from_ref, to_ref=to_ref)
    log = get_log(repo, n=20, from_ref=from_ref, to_ref=to_ref if from_ref else "")
    style = state.get("style", "compact")
    guide = _STYLE_GUIDE.get(style, _STYLE_GUIDE["compact"])

    if not diff and not log:
        return {"generated_docs": [{"name": "CHANGELOG", "file": "CHANGELOG.md", "generated_doc": "No changes detected."}]}

    log_text = "\n".join(
        f"[{c['hash']}] {c['author']} — {c['message']}" for c in log
    )
    # Cap diff size to avoid token overflow
    diff_truncated = diff[:8000] + ("\n... (truncated)" if len(diff) > 8000 else "")

    prompt = (
        f"Style: {guide}\n\n"
        f"Recent commits:\n{log_text or '(none)'}\n\n"
        f"Git diff:\n```diff\n{diff_truncated}\n```\n\n"
        "Generate a changelog entry for these changes."
    )

    llm = get_llm("model")
    messages = [SystemMessage(content=_SYSTEM), HumanMessage(content=prompt)]
    try:
        with spinning("Writing changelog"):
            response = llm.invoke(messages)
    except Exception as e:
        raise classify_llm_error(e) from e

    token_actual = state.get("token_actual", 0)
    meta = getattr(response, "usage_metadata", None)
    if meta:
        token_actual += meta.get("total_tokens", 0) or (
            meta.get("input_tokens", 0) + meta.get("output_tokens", 0)
        )

    changelog_doc = {
        "name": "CHANGELOG.md",
        "file": "CHANGELOG.md",
        "generated_doc": response.content,
    }
    return {"generated_docs": [changelog_doc], "token_actual": token_actual}
