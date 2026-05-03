# Changelog

All notable changes are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.1.1] - 2026-05-03

### Added

**README generation pipeline**
- `dp readme` — generate or update `README.md` using project context and git signals
- `dp readme --dry-run` — preview LLM context and token estimate without writing
- `dp readme --rewrite` — regenerate from scratch, ignoring existing README
- `dp readme --output <path>` — write README to a custom path
- `dp readme --remarks "<note>"` — pass extra instructions to the LLM
- `<!-- dp-keep -->...<!-- /dp-keep -->` blocks preserved across rewrites
- Diff-aware: skips generation when nothing changed since last run
- Interactive review before writing — accept, request changes, or abort
- Collects: `pyproject.toml` metadata, directory tree, public API surface, git history signals, test coverage summary, existing README

**README smart compaction**
- Existing READMEs over 4 000 chars are compacted (headings + first paragraphs) instead of hard-truncated
- LLM receives structured skeleton that preserves meaning without wasting tokens

### Changed

- Node modules reorganised into `src/graph/nodes/docstring/` and `src/graph/nodes/readme/` subdirectories
- `dp config` now shows a single interactive view with edit/reset shortcuts instead of subcommands
- `CompiledDocpatchGraph` and `CompiledReadmeGraph` type aliases updated to 4-param `CompiledStateGraph` (matches LangGraph 1.1.9)
- Error chain preserved through `handle_stream_error` — `--debug` now shows full original traceback

### Fixed

- **State corruption in docstring fan-out**: `fan_out_batches` was calling `.model_dump()` before passing state via `Send`, converting `DocpatchState` to a plain dict. Subsequent nodes (`writer`, `cache_update`) accessed `.dry_run` as an attribute and raised `AttributeError`. Fix: send `model_copy()` directly.
- **Python 2 except syntax** in `readme_signals.py`: `except OSError, SyntaxError:` raised `SyntaxError` on Python 3. Fixed to `except (OSError, SyntaxError) as _:`.

---

## [0.1.0] - 2026-04-30

Initial release. Core docstring generation is stable. README, changelog generation, and code review commands are planned but not yet implemented.

### Added

**Core pipeline**
- Git-aware scanner — only functions that changed or are undocumented get sent to the LLM
- `--since <ref>` scopes scanning to files changed between a git ref and HEAD (committed range)
- LibCST-based safe AST rewrite — no regex, no string replacement
- Body hash cache — unchanged functions are never re-sent across runs
- Batch fan-out via LangGraph `Send` — parallel LLM calls per batch
- SQLite checkpointing — interrupted runs resume from last checkpoint with `--resume`

**LLM**
- Providers: Google Gemini, OpenAI, Anthropic (BYOK)
- Structured output via `with_structured_output` — no JSON parsing in prompts
- Rate limit retry with exponential backoff (60s → 120s, up to 10 retries)
- Network error auto-retry with exponential backoff (5s → 60s, up to 5 retries)
- Provider/model switch on rate limit without restarting
- `--style compact|detailed` for docstring verbosity

**CLI**
- `dp docs` — generate docstrings interactively
- `dp docs --dry-run` — preview scope and estimated token cost, no LLM calls
- `dp docs --check` — CI/pre-commit mode, exits 1 if any functions need documentation
- `dp docs --update` — re-document all functions, ignore cache
- `dp setup` — interactive provider, API key, and style setup
- `dp config show|set|edit` — view and modify configuration
- `dp cleanup` — remove local data interactively
- `--debug` flag — structured log output via Rich to stderr

**Ignore system**
- `.docsignore` at repo root (gitignore syntax)
- Always-ignored defaults: `tests/`, `__init__.py` files
- `# dp: ignore` comment above any function to permanently skip it

**Review session**
- Interactive per-function review before any writes (accept, edit, rerun)
- Bulk accept option
- Rerun with optional LLM guidance note
- Ctrl+C preserves accepted docstrings so far
