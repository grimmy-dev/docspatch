# docpatch — Full Project Context

## What it is
A BYOK Python CLI tool that automatically generates and updates code documentation.
Git-aware, token-efficient, never touches the filesystem without user confirmation.
Alias: `dp`

## Target user
Developers who write their own code and keep forgetting to document it.

## Core philosophy
- Never write to filesystem without user confirmation
- Only process what actually changed — not the whole repo
- Filter trivial changes before any LLM call — no token waste
- Agents only where LLM judgment is needed, pure Python everywhere else
- Ship tight, ship working — no feature creep in V1

---

## Commands — V1 only

```bash
dp init                  # cold start — scan repo, prioritize by coverage
dp docs [path]           # in-file docstrings for changed functions
dp readme [path]         # generate or update README.md
dp clg                   # changelog from git diff
dp review [path]         # code quality feedback
```

## Flags
```bash
--style compact|detailed # default set in config
--dry-run                # estimate tokens/cost, no LLM calls
--tokens                 # show actual usage + cost after run
--batch                  # force batch mode
```

---

## Stack

| Layer            | Choice                              |
|------------------|-------------------------------------|
| CLI              | Typer                               |
| Terminal UI      | Rich                                |
| Orchestration    | LangGraph                           |
| LLM abstraction  | LangChain core                      |
| AST parsing      | Python `ast` module (V1, Python only)|
| Git              | GitPython                           |
| Config           | TOML — `~/.docpatch/config.toml`    |
| Cache            | JSON — `~/.docpatch/cache.json`     |
| Packaging        | pyproject.toml — `pip install docpatch` |

---

## Project Structure

```
docpatch/
├── cli/
│   └── main.py                  # Typer entry point, routes to graphs
├── graph/
│   ├── state.py                 # DocpatchState TypedDict
│   ├── nodes/
│   │   ├── scanner.py           # file walk — pure Python
│   │   ├── hash_check.py        # file + function level hashing — pure Python
│   │   ├── ast_parser.py        # extract functions, line numbers — pure Python
│   │   ├── significance.py      # diff filter, ignore trivial changes — pure Python
│   │   ├── size_check.py        # large repo detection — pure Python
│   │   ├── batcher.py           # group functions for LLM — pure Python
│   │   ├── docwriter.py         # LLM node
│   │   ├── reviewer.py          # LLM node
│   │   ├── readme_writer.py     # LLM node
│   │   ├── clg_writer.py        # LLM node
│   │   ├── preview.py           # Rich UI, user interaction — pure Python
│   │   └── writer.py            # inject docs to filesystem — pure Python
│   └── graphs/
│       ├── docs_graph.py
│       ├── readme_graph.py
│       ├── clg_graph.py
│       ├── review_graph.py
│       └── init_graph.py
├── utils/
│   ├── cache.py                 # hash read/write
│   ├── git.py                   # diff, log, branch helpers
│   ├── config.py                # TOML read/write
│   └── differ.py                # significance logic
├── config.toml.example
└── pyproject.toml
```

---

## State

```python
class DocpatchState(TypedDict):
    # context
    command: str
    target_path: str
    style: str                        # compact | detailed
    is_init: bool

    # files
    files: list[str]
    changed_files: list[str]

    # parsed functions — each dict contains:
    # name, file, line_start, line_end,
    # signature, body, existing_doc,
    # body_hash, is_significant
    parsed_functions: list[dict]

    # batching
    needs_batching: bool
    batch_strategy: str               # auto | pick | smart
    batches: list[list[dict]]

    # LLM output
    generated_docs: list[dict]
    accepted_docs: list[dict]
    skipped_docs: list[dict]
    feedback: dict[str, str]          # function name → user feedback text
    rerun_docs: list[dict]            # regenerated after feedback

    # tokens + flags
    doc_coverage: dict[str, int]      # file → % documented
    token_estimate: int
    token_actual: int
    show_tokens: bool
    dry_run: bool
```

---

## Graph Flow — docs command (canonical reference)

```
scanner
   ↓
hash_check ──── all unchanged ──────────────────────→ EXIT
   ↓
ast_parser
   ↓
significance ── all trivial ────────────────────────→ EXIT
   ↓
size_check ──── too large ──→ prompt user strategy
   ↓                                    ↓
batcher ←───────────────────────────────┘
   ↓
docwriter (LLM)
   ↓
preview_all
   ↓
bulk_accept ──── all accepted ──→ writer ──→ cache_update ──→ done
   ↓
individual_review (per function [a]accept [s]skip)
   ↓
writer ──→ cache_update
   ↓
rerun_check ──── skipped exist? ──→ feedback_collect ──→ docwriter (cycle)
   ↓
done
```

---

## Three filter layers before any LLM call

1. **File hash check** — file unchanged since last run → skip entirely
2. **Function hash check** — file changed but this function unchanged → skip this function
3. **Significance check** — function changed but only whitespace, comma, spacing → skip, not meaningful

Only what survives all three goes to docwriter. This is where token efficiency lives.

---

## AST — how positioning works

Python `ast` gives exact line numbers. No regex, no guessing:

```python
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef):
        start = node.lineno        # where function starts
        end = node.end_lineno      # where function ends
```

Each parsed function in state stores `line_start` and `line_end`.
Writer node uses these to inject docstring at the exact right position.
If existing docstring present — overwrite in place using same line numbers.

---

## Large repo handling

Size check node runs after AST parse. If too large, prompt user:

```
  ⚠  Large repo detected — 847 functions across 34 files
     Estimated cost: ~$0.12 on gpt-4o-mini

  [a] auto-batch  — process in chunks
  [p] pick files  — choose which files now
  [s] smart       — only undocumented functions
  [q] quit
```

Smart mode skips anything that already has a docstring — best default for large existing repos.

`dp init` for cold start prioritizes files by: most imported + least doc coverage.

---

## UX feel

```
$ dp docs src/auth.py

  Scanning...          done
  Hash check...        2 unchanged  1 changed
  Significance...      1 meaningful change
  Generating...        done

  ┌─ 1/1  generate_token() ─────────────────────┐
  │  Generates a signed JWT for the given user   │
  │  ID and expiry. Raises ValueError if user    │
  │  ID is empty.                                │
  │  Args: user_id (str), expiry (int)           │
  │  Returns: str                                │
  └──────────────────────────────────────────────┘

  Accept all? [y] review individually [r] quit [q]: y

  Writing...           done  1 file updated
```

Skipped docs flow:
```
  2 skipped. Rerun with feedback? [y/n]: y

  ┌─ validate_token() ──────────────────────────┐
  │  Current: "Validates a JWT token..."         │
  └──────────────────────────────────────────────┘

  What's wrong?: too vague, mention error handling

  Regenerating...  done
  [a] accept  [s] skip
```

---

## Key decisions — do not revisit these in V1

- Python only via `ast` module — tree-sitter is V2
- No auto-writes ever — user always confirms before filesystem change
- Tiered models — cheap model for docs, stronger only for review
- BYOK — user brings their own API key via config
- LangGraph nodes can be pure Python — LLM only in docwriter, reviewer, readme_writer, clg_writer
- `dp init` does not doc everything — it prioritizes and asks first
- Significance filter must normalize whitespace before comparing — spaces never trigger LLM

---

## Tooling
- Package manager: uv
- Never use pip
- Install deps: uv add <package>
- Run code: uv run python -m <module>

## Config shape

```toml
# ~/.docpatch/config.toml

[defaults]
style = "compact"
model = "gpt-4o-mini"
review_model = "gpt-4o"

[keys]
openai_api_key = "sk-..."
# or
anthropic_api_key = "sk-ant-..."
```

---

## V2 backlog — do not touch in V1

- tree-sitter for multi-language (JS, TS, Rust, Go)
- `dp onboard` — generates ONBOARDING.md
- `dp pr` — PR description from branch diff
- `dp watch` — git hook / pre-commit mode
- `--out notion` output target
- Rust CLI rewrite
- `--persona junior` for team onboarding
- `dp audit` — staleness detection, docs not updated with code
- `dp clg --team` — changelog grouped by contributor