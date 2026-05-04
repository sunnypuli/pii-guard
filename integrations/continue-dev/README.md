# pii-guard × Continue.dev

Continue.dev is an open-source AI coding assistant for VS Code and JetBrains. Set a custom `apiBase` in its config to route through pii-guard.

## Setup

**1. Start the proxy**

```bash
pii-guard proxy --port 8111 --preset dpdp
```

**2. Edit `~/.continue/config.json`**

For Anthropic models:

```json
{
  "models": [
    {
      "title": "Claude (via pii-guard)",
      "provider": "anthropic",
      "model": "claude-sonnet-4-6",
      "apiBase": "http://localhost:8111",
      "apiKey": "YOUR_ANTHROPIC_KEY"
    }
  ]
}
```

For OpenAI models:

```json
{
  "models": [
    {
      "title": "GPT-4o (via pii-guard)",
      "provider": "openai",
      "model": "gpt-4o",
      "apiBase": "http://localhost:8111/openai/v1",
      "apiKey": "YOUR_OPENAI_KEY"
    }
  ]
}
```

Reload Continue (Cmd+Shift+P → `Continue: Reload`). All prompts — inline edits, chat, slash commands — are now filtered.

## Restore real values

```bash
pii-guard detokenize output.txt --session ~/.pii-guard/sessions/<session-id>.json
```
