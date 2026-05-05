# piiwall × OpenAI Codex CLI

The OpenAI Codex CLI respects `OPENAI_BASE_URL`. Route it through piiwall in one line.

## Setup

**1. Start the proxy**

```bash
piiwall proxy --port 8111 --preset dpdp
```

**2. Run Codex with the proxy**

```bash
OPENAI_BASE_URL=http://localhost:8111/openai/v1 codex "analyse this file"
```

Or export permanently for the session:

```bash
export OPENAI_BASE_URL=http://localhost:8111/openai/v1
codex "analyse customers.csv"
```

## Restore real values

```bash
piiwall detokenize output.txt --session ~/.piiwall/sessions/<session-id>.json
```

## Notes

- Works with all Codex CLI commands — `codex`, `codex chat`, `codex run`.
- Use `--preset dpdp,pci` to cover both Indian PII and payment card data.
