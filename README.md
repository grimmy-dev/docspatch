# docspatch

BYOK CLI that auto-generates and updates Python docstrings, READMEs, and changelogs — using your own API key, only on what changed.

```
$ dp docs src/auth.py

  ◈ docspatch  v0.1.0

  ✓  Scanning              1 Python file
  ✓  Hash check            1 changed, 0 unchanged
  ✓  Parsing               3 functions
  ✓  Significance          3 meaningful
  ✓  Generating            3 docstrings ready  [1,240 tokens]

  src/auth.py
    generate_token()   Generate a signed JWT for the given user ID.
    verify_token()     Verify and decode a JWT, raising ValueError if invalid.
    refresh_session()  Extend session expiry for an authenticated user.

  3 docs ready
  ? Review mode: › Accept all / Review individually
```

## Install

```bash
uv tool install docspatch
```

## First run

```bash
dp setup    # choose provider, enter API key, set default style
```

## Commands

```bash
dp init                  # cold start — scan whole repo, document undocumented functions
dp docs [path]           # generate/update docstrings for changed functions
dp readme [path]         # generate or update README.md
dp clg                   # changelog from git diff
dp review [path]         # code quality feedback
dp config show           # show current config
dp config set <key>      # update a config value (interactive for model/provider)
dp setup                 # re-run onboarding wizard
dp cleanup               # remove ~/.docspatch/ (config + cache)
```

## Flags

```bash
--style compact|detailed  # override style for this run (default reads from config)
--dry-run                 # estimate tokens/cost, no LLM calls
--tokens                  # accepted (no-op; token count always shown)
--batch                   # force batch mode for large repos
```

## Config

Config lives at `~/.docspatch/config.toml`. Edit directly or use `dp config set`.

```toml
[defaults]
style        = "compact"          # compact | detailed
model        = "gemini-2.5-flash" # model used for docs/readme/clg
review_model = "gemini-2.5-flash" # model used for dp review
provider_key = "google_api_key"   # which key is active

[keys]
google_api_key    = "AIza..."
# openai_api_key  = "sk-..."
# anthropic_api_key = "sk-ant-..."
```

Multiple provider keys can be stored at once. `provider_key` controls which is active.

### Change model

```bash
dp config set model           # interactive select from provider's model list
dp config set review_model    # same, for the review model
```

### Switch provider

```bash
dp config set provider        # wizard: select provider, reuse stored key or enter new, pick models
```

If the selected provider already has a stored key, you are offered to reuse it — no need to re-enter.

## Providers

| Provider | Key field | Models |
|----------|-----------|--------|
| Google Gemini | `google_api_key` | gemini-2.5-flash, gemini-2.5-pro, gemini-2.5-flash-lite |
| OpenAI | `openai_api_key` | gpt-5.4, gpt-5.4-mini, gpt-5.4-nano, … |
| Anthropic | `anthropic_api_key` | claude-haiku-4-5, claude-sonnet-4-6, claude-opus-4-7 |

## How it works

Three filter layers before any LLM call:

1. **File hash** — file unchanged since last run → skip entirely
2. **Function hash** — file changed but this specific function unchanged → skip
3. **Significance** — only whitespace/comments changed → skip

Only what survives all three goes to the LLM.

Preview flow: generated docs are always shown before you decide — bulk table (docstrings) or truncated panel (README/CHANGELOG) — then choose Accept all or review individually. Individual review supports Accept, Edit manually, Regenerate (with feedback to LLM), or Discard.

## Styles

| Style | Output |
|-------|--------|
| `compact` | One-sentence summary per function |
| `detailed` | Full Google-style: summary, Args, Returns, Raises |

Set default in config (`style = "detailed"`) or override per-run with `--style detailed`.

## Uninstall

```bash
dp cleanup
uv tool uninstall docspatch
```

## License

[MIT](LICENSE)
