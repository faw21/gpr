# gpr — AI-powered PR descriptions from your git diff

Stop writing PR descriptions by hand. `gpr` analyzes your branch diff and commit history, then generates a professional PR description in seconds — using Claude, OpenAI, or a **local Ollama model** (no API key required).

```
$ gpr
Branch: feature/auth → main  |  3 commits, 5 files changed, +247/-31 lines

╭─────────────────────── PR Description ──────────────────────────╮
│ **Title:** Add JWT authentication with refresh token support     │
│                                                                  │
│ ## Summary                                                       │
│ Implements JWT-based authentication replacing the session-based  │
│ system. Adds refresh token rotation for better security and...   │
│                                                                  │
│ ## Changes                                                       │
│ - `src/auth/jwt.py`: New JWT encode/decode with HS256            │
│ - `src/middleware/auth.py`: Updated auth middleware for JWT      │
│ - `tests/test_auth.py`: 14 new tests covering edge cases        │
│                                                                  │
│ ## Test Plan                                                     │
│ - [ ] Login flow generates valid JWT                            │
│ - [ ] Expired tokens are rejected with 401                      │
│ - [ ] Refresh token rotation works correctly                    │
╰──────────────────────────────────────────────────────────────────╯
```

## Why gpr?

| Tool | What it does | Limitation |
|------|-------------|------------|
| aicommits | Generates commit messages | Only commit messages, not PR descriptions |
| GitHub Copilot | Suggests PR description in browser | Requires GitHub Copilot subscription |
| **gpr** | **Full PR description from git diff** | **Works with any provider, including local LLMs** |

Key advantages:
- **No vendor lock-in** — Claude, OpenAI, or local Ollama
- **No API key required** — use `--provider ollama` with a local model
- **PR-focused** — understands commit history, file changes, and context
- **Integrates with `gh`** — one flag to open `gh pr create` with generated content

## Install

```bash
pip install gpr-ai
```

Or with [pipx](https://pipx.pypa.io/):
```bash
pipx install gpr-ai
```

## Quick Start

```bash
# Generate PR description (Claude, requires ANTHROPIC_API_KEY)
gpr

# Use local Ollama — no API key needed!
gpr --provider ollama --model llama3.2

# Use OpenAI
OPENAI_API_KEY=sk-... gpr --provider openai

# Copy to clipboard
gpr --copy

# Open gh pr create directly
gpr --gh

# Save to file
gpr --output pr.md
```

## Usage

```
Usage: gpr [OPTIONS]

  Generate AI-powered pull request descriptions from your git diff.

Options:
  -p, --provider [claude|openai|ollama]
                                  AI provider to use.  [default: claude]
  -m, --model TEXT                Model name (provider-specific).
  -b, --base TEXT                 Base branch to diff against (auto-detected).
  -s, --style [standard|conventional|minimal]
                                  PR description style.  [default: standard]
  -c, --copy                      Copy output to clipboard.
  --gh                            Open 'gh pr create' with generated content.
  -o, --output PATH               Save output to file.
  --raw                           Print raw markdown without rich formatting.
  --diff-only                     Print the diff that would be sent to AI.
  --ollama-host TEXT              Ollama server URL.  [default: http://localhost:11434]
  --repo PATH                     Path to git repository.
  --version                       Show the version and exit.
  --help                          Show this message and exit.
```

## PR Styles

### `standard` (default)
Full PR description with Summary, Changes, and Test Plan sections.

### `conventional`
Follows [Conventional Commits](https://www.conventionalcommits.org/) format with type/scope prefix.

### `minimal`
Brief title + 3 bullet points. Good for small changes.

```bash
gpr --style conventional
gpr --style minimal
```

## Using Local Models (Ollama)

No API key required — runs entirely on your machine:

```bash
# Install Ollama: https://ollama.ai
ollama pull llama3.2   # or codellama, mistral, etc.

# Run gpr with Ollama
gpr --provider ollama --model llama3.2
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Required for `--provider claude` |
| `OPENAI_API_KEY` | Required for `--provider openai` |

## Workflow Integration

### With `gh` CLI
```bash
# Generate and immediately create PR
gpr --gh

# Or save first, review, then create
gpr --output pr.md
cat pr.md  # review
gh pr create --title "..." --body "$(cat pr.md)"
```

### In CI (generate PR description on push)
```bash
gpr --raw --provider ollama > pr_description.md
```

## Requirements

- Python 3.9+
- Git repository with at least one commit
- One of: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or running Ollama

## License

MIT
