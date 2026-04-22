# docspatch — Task Checklist

Always tell Claude Code: "check TASKS.md, let's do the next unchecked item"

---

## Phase 1 — Scaffold

- [x] `pyproject.toml` — project metadata, dependencies, `dp` entry point
- [x] `config.toml.example` — template for user config
- [x] `cli/main.py` — Typer app skeleton, all commands stubbed
- [x] `graph/state.py` — `DocpatchState` TypedDict, fully typed

## Phase 2 — Pure Python Nodes

- [x] `utils/config.py` — read/write `~/.docspatch/config.toml`
- [x] `utils/cache.py` — read/write `~/.docspatch/cache.json`
- [x] `utils/git.py` — diff, log, changed files helpers
- [x] `utils/differ.py` — significance check logic, whitespace normalization
- [x] `graph/nodes/scanner.py` — walk files, respect .gitignore
- [x] `graph/nodes/hash_check.py` — file level + function level hash diff
- [x] `graph/nodes/ast_parser.py` — extract functions with line_start, line_end, signature, body, existing_doc
- [x] `graph/nodes/significance.py` — filter trivial changes before LLM
- [x] `graph/nodes/size_check.py` — detect large repos, prompt batch strategy
- [x] `graph/nodes/batcher.py` — group functions for efficient LLM calls
- [x] `graph/nodes/preview.py` — Rich UI panels, bulk accept/skip flow
- [x] `graph/nodes/writer.py` — inject docstrings at exact line positions

## Phase 3 — LLM Nodes

- [x] `graph/nodes/docwriter.py` — compact/detailed docstring generation
- [x] `graph/nodes/reviewer.py` — code quality feedback
- [x] `graph/nodes/readme_writer.py` — README generation
- [x] `graph/nodes/clg_writer.py` — changelog from git diff

## Phase 4 — Graphs

- [x] `graph/graphs/docs_graph.py` — full docs flow wired end to end
- [x] `graph/graphs/review_graph.py`
- [x] `graph/graphs/readme_graph.py`
- [x] `graph/graphs/clg_graph.py`
- [x] `graph/graphs/init_graph.py`

## Phase 5 — Wire CLI to Graphs

- [x] `dp docs` command fully working end to end
- [x] `dp review` command fully working
- [x] `dp readme` command fully working
- [x] `dp clg` command fully working
- [x] `dp init` command fully working

## Phase 6 — Flags

- [x] `--style compact|detailed` working across all commands
- [x] `--dry-run` token estimate before any LLM call
- [x] `--tokens` show usage + cost after run
- [x] `--batch` force batch mode

## Phase 7 — Polish

- [x] Error handling — missing config, no git repo, unsupported file type
- [x] Empty state exits with helpful messages
- [x] `dp --help` clean and readable
- [x] UI/UX — step progress, spinners, no silent processing
- [x] `dp cleanup` — remove ~/.docspatch/, show uninstall instructions
- [x] LICENSE — MIT
- [x] README.md for docspatch itself
- [x] `dp setup` onboarding — provider selection, API key, style preference
- [x] `dp config show/set` — view and update settings from CLI
- [x] Writer fixed for full-file mode (README, CHANGELOG)
- [x] LICENSE field in pyproject.toml
- [ ] Test on a real Python repo

---

## Done

- `pyproject.toml` — project metadata, dependencies, `dp` entry point
- `config.toml.example` — template for user config
- `cli/main.py` — Typer app skeleton, all commands stubbed
- `graph/state.py` — `DocpatchState` TypedDict, fully typed
