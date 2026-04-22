# docspatch

BYOK CLI that auto-generates and updates Python docstrings, READMEs, and changelogs — using your own API key, only on what changed.

```
$ dp docs src/auth.py

  ✓  Scanning              1 Python file
  ✓  Hash check            1 changed, 0 unchanged
  ✓  Parsing               3 functions
  ✓  Significance          3 meaningful
  Generating...
  ✓  Generating            3 docstrings ready

  ┌─ 1/3  generate_token() ───────────────────────┐
  │  Generate a signed JWT for the given user ID  │
  │  and expiry. Raises ValueError if empty.      │
  └───────────────────────────────────────────────┘

  Accept all? [y] review individually [r] quit [q]: y

  ✓  Writing               1 file updated
```

## Install

```bash
# Global install — dp available everywhere
pip install docspatch

# or with uv (recommended)
uv tool install docspatch
```

## First run

```bash
dp setup    # choose provider, enter API key, set style
```

## Setup

Create `~/.docspatch/config.toml`:

```toml
[defaults]
style = "compact"               # compact | detailed
model = "gemini-2.0-flash"
review_model = "gemini-2.5-pro"

[keys]
google_api_key = "AIza..."
# openai_api_key = "sk-..."
# anthropic_api_key = "sk-ant-..."
```

Supports Google Gemini, OpenAI, and Anthropic. One key is enough.

## Commands

```bash
dp init                  # cold start — scan repo, prioritize by coverage
dp docs [path]           # generate/update docstrings for changed functions
dp readme [path]         # generate or update README.md
dp clg                   # changelog from git diff
dp review [path]         # code quality feedback
```

## Flags

```bash
--style compact|detailed  # default set in config
--dry-run                 # estimate tokens/cost, no LLM calls
--tokens                  # show actual token usage after run
--batch                   # force batch mode
```

## How it works

Three filter layers before any LLM call:

1. **File hash** — file unchanged since last run → skip entirely
2. **Function hash** — file changed but this function unchanged → skip
3. **Significance** — only whitespace/comments changed → skip

Only what survives all three goes to the LLM.

## Uninstall

```bash
dp cleanup               # remove ~/.docspatch/ (config + cache)
pip uninstall docspatch
```

## License

[MIT](LICENSE)
