from typing import TypedDict


class DocpatchState(TypedDict):
    # context
    command: str
    target_path: str
    style: str          # compact | detailed
    is_init: bool
    from_ref: str       # clg: start commit/tag (empty = all history)
    to_ref: str         # clg: end commit/tag (empty = HEAD)

    # files
    files: list[str]
    changed_files: list[str]

    # parsed functions — each dict: name, file, line_start, line_end,
    # signature, body, existing_doc, body_hash, is_significant
    parsed_functions: list[dict]

    # batching
    needs_batching: bool
    batch_strategy: str  # auto | pick | smart
    batches: list[list[dict]]

    # LLM output
    generated_docs: list[dict]
    accepted_docs: list[dict]
    skipped_docs: list[dict]
    feedback: dict[str, str]   # function name → user feedback
    rerun_docs: list[dict]

    # tokens + flags
    doc_coverage: dict[str, int]  # file → % documented
    token_estimate: int
    token_actual: int
    show_tokens: bool
    dry_run: bool
