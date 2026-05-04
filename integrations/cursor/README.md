# pii-guard × Cursor

Cursor uses the OpenAI API under the hood. Point it at the pii-guard proxy and every prompt is sanitized before it leaves your machine.

## Setup

**1. Start the proxy**

```bash
pii-guard proxy --port 8111 --preset dpdp
```

**2. Set the base URL in Cursor**

Open Cursor Settings → `Cursor Settings` → `Models` → `OpenAI API Key` section → toggle **Override OpenAI Base URL**:

```
http://localhost:8111/openai/v1
```

Or set the env var before launching Cursor:

```bash
export OPENAI_BASE_URL=http://localhost:8111/openai/v1
cursor .
```

That's it. Every prompt Cursor sends — inline edits, chat, Cmd+K — passes through pii-guard.

## Restore real values

```bash
pii-guard detokenize output.txt --session ~/.pii-guard/sessions/<session-id>.json
# or export as CSV
pii-guard export-session ~/.pii-guard/sessions/<session-id>.json
```

## Notes

- The proxy must be running before you open Cursor.
- Use `PII_GUARD_PRESETS=dpdp,pci` to activate multiple presets.
- Restart the proxy to start a new session key.
