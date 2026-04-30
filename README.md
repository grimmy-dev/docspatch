# docspatch

> **Still in development.** Core docstring generation works and is stable.
> README, changelog, and code review features are not yet implemented.
> Not published to PyPI until remaining features are complete.

BYOK CLI that auto-generates and updates Python docstrings from your git diff.
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
dp setup          # pick provider, enter API key, choose style
dp docs           # document undocumented or changed functions
dp docs --dry-run # preview what would be documented, no writes
```

---

## Commands

| Command | Description |
|---|---|
| `dp docs` | Generate docstrings for undocumented/changed functions |
| `dp docs --dry-run` | Preview scope and estimated cost, no LLM calls |
| `dp docs --check` | Exit 1 if any functions need documentation (CI/pre-commit) |
| `dp docs --update` | Re-document all functions, ignore cache |
| `dp docs --since <ref>` | Limit to files changed between `<ref>` and HEAD (committed range) |
| `dp docs --resume` | Resume an interrupted run |
| `dp setup` | Interactive provider and style configuration |
| `dp config show` | Print current settings and masked API keys |
| `dp config set provider` | Switch provider interactively |
| `dp config edit` | Open config file in your default editor |
| `dp cleanup` | Remove local data (cache, checkpoints, logs, config) |

---

## Configuration

Config lives at `~/.docspatch/config.toml`. Edit directly or via `dp config edit`.

| Key | Default | Description |
|---|---|---|
| `style` | `compact` | Docstring style: `compact` or `detailed` |
| `model` | `gemini-2.5-flash` | Generation model |
| `review_model` | `gemini-2.5-pro` | Review model |
| `provider_key` | `Google Gemini` | Active provider |
| `batch_size` | `5` | Functions per LLM batch |
| `diff_cap` | `200` | Max function lines — larger functions are skipped |
| `large_threshold` | `50` | Function count above which docspatch prompts before running |

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

1. Scans tracked git files for Python functions
2. Compares body hashes against a local cache — skips anything unchanged
3. Batches changed/undocumented functions and sends them to the LLM
4. Puts you in an interactive review session before writing anything
5. Writes accepted docstrings back to source using LibCST (safe AST rewrite)
6. Updates the cache so unchanged functions are never re-sent

---

## License

MIT — see [LICENSE](LICENSE).
