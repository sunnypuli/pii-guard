# pii-guard × Aider

Aider is a terminal-based AI coding assistant. Route it through the pii-guard proxy so PII in your files never reaches OpenAI or Anthropic servers.

## Setup

**1. Start the proxy**

```bash
# For OpenAI / GPT models
pii-guard proxy --port 8111 --preset dpdp

# For Anthropic / Claude models
pii-guard proxy --port 8112 --preset dpdp
```

**2. Run aider with the proxy base URL**

```bash
# OpenAI models
OPENAI_API_BASE=http://localhost:8111/openai/v1 aider --model gpt-4o

# Anthropic models
ANTHROPIC_BASE_URL=http://localhost:8112 aider --model claude-sonnet-4-6
```

Or export once and use aider normally:

```bash
export OPENAI_API_BASE=http://localhost:8111/openai/v1
aider
```

## Restore real values

```bash
pii-guard detokenize .aider.chat.history.md --session ~/.pii-guard/sessions/<session-id>.json
```

## Notes

- Aider uses `OPENAI_API_BASE` (not `OPENAI_BASE_URL`) — both work with the proxy but the env var name matters for aider.
- The proxy handles streaming responses, so `/diff`, `/commit`, and chat all work normally.
- Session key is shared across the proxy's lifetime — one export-session covers the full aider session.
