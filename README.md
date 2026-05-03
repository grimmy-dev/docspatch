# docspatch

BYOK CLI that auto-generates Python docstrings and README files from your git diff.
Only functions that changed or are undocumented get sent to the LLM — nothing else.

**Providers**: Google Gemini · OpenAI · Anthropic  
**Issues**: https://github.com/grimmy-dev/docspatch/issues

---

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- A git repository
- An API key for Gemini, OpenAI, or Anthropic

---

## Install

```bash
git clone https://github.com/grimmy-dev/docspatch
cd docspatch
uv sync
```

Run via:

```bash
uv run dp <command>
```

Or install globally:

```bash
uv tool install .
dp <command>
```

---

## Quick start

```bash
dp setup           # pick provider, enter API key, choose style
dp docs            # document undocumented or changed functions
dp docs --dry-run  # preview scope and estimated cost, no writes
dp readme          # generate or update README.md
dp readme --dry-run  # preview what the LLM would receive, no writes
```

---

## Commands

### Docstrings

| Command | Description |
|---|---|
| `dp docs` | Generate docstrings for undocumented/changed functions |
| `dp docs --dry-run` | Preview scope and estimated cost, no LLM calls |
| `dp docs --check` | Exit 1 if any functions need documentation (CI/pre-commit) |
| `dp docs --update` | Re-document all functions, ignore cache |
| `dp docs --since <ref>` | Limit to files changed between `<ref>` and HEAD |
| `dp docs --resume` | Resume an interrupted run |
| `dp docs --style compact\|detailed` | Override style for this run |

### README

| Command | Description |
|---|---|
| `dp readme` | Generate or update `README.md` interactively |
| `dp readme --dry-run` | Preview LLM context and token estimate, no writes |
| `dp readme --rewrite` | Regenerate from scratch, ignore existing README |
| `dp readme --output <path>` | Write to a custom path instead of `README.md` |
| `dp readme --style compact\|detailed` | Override style (compact = minimal, detailed = badges + full sections) |
| `dp readme --remarks "<note>"` | Pass extra instructions to the LLM |

### Setup and config

| Command | Description |
|---|---|
| `dp setup` | Interactive provider, API key, and style setup |
| `dp config` | View current settings and API keys (with shortcuts to edit/reset) |
| `dp cleanup` | Remove local data (cache, checkpoints, logs, config) |

---

## Configuration

Config lives at `~/.docspatch/config.toml`. Edit directly or via `dp config`.

| Key | Default | Description |
|---|---|---|
| `style` | `compact` | Docstring style: `compact` or `detailed` |
| `model` | `gemini-2.5-flash` | Generation model |
| `review_model` | `gemini-2.5-pro` | Review/README model |
| `provider_key` | `Google Gemini` | Active provider |
| `batch_size` | `5` | Functions per LLM batch |
| `diff_cap` | `200` | Max function lines — larger functions are skipped |
| `large_threshold` | `50` | Function count above which docspatch prompts before running |
| `readme_tokens_compact` | — | Token budget for compact README generation |
| `readme_tokens_detailed` | — | Token budget for detailed README generation |

---

## Ignoring files and folders

Create `.docsignore` at your repo root. Uses gitignore syntax.

```
# ignore generated code
src/generated/
migrations/
```

**Always ignored by default**: `tests/`, `__init__.py` files.

---

## Skipping individual functions

Place `# dp: ignore` on the line immediately above a function definition:

```python
# dp: ignore
def internal_hack():
    ...
```

docspatch will never document that function.

---

## Preserving README sections

Wrap any section you want to protect from rewrites:

```markdown
<!-- dp-keep -->
## Custom Section

This block is preserved across `dp readme` runs.
<!-- /dp-keep -->
```

---

## Pre-commit usage

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: docspatch-check
      name: docspatch check
      entry: dp docs --check
      language: system
      types: [python]
      pass_filenames: false
```

Exits 1 and lists undocumented/changed functions. No LLM calls.

---

## Resuming interrupted runs

If a run is interrupted (Ctrl+C, network drop), resume it:

```bash
dp docs --resume
```

Checkpoints are stored in `~/.docspatch/checkpoints.db`.

---

## How it works

### Docstrings

1. Scans tracked git files for Python functions
2. Compares body hashes against a local cache — skips anything unchanged
3. Batches changed/undocumented functions and sends them to the LLM in parallel
4. Puts you in an interactive review session before writing anything
5. Writes accepted docstrings back to source using LibCST (safe AST rewrite)
6. Updates the cache so unchanged functions are never re-sent

### README

1. Collects project context: `pyproject.toml`, directory tree, public API surface, git signals, test coverage
2. Compares against HEAD — skips generation if nothing changed
3. Sends context to the LLM with your existing README as reference
4. Presents the generated README for review before writing
5. Preserves `<!-- dp-keep -->` blocks from the original

---

## License

MIT — see [LICENSE](LICENSE).
