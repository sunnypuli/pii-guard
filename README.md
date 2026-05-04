# pii-guard

**Local PII firewall for AI CLI tools. Tokenize before it leaves your machine.**

When you ask Claude Code or Codex to analyse data, raw PII — Aadhaar numbers, emails, PANs, phone numbers — travels to Anthropic/OpenAI servers. pii-guard intercepts it first, replaces real values with consistent tokens (`[AADHAAR_1]`, `[EMAIL_2]`), and lets the analysis run on the safe version. You keep the key file; you can reverse it any time.

## Install

```bash
pip install pii-guard
```

## Quickstart

```bash
# Scan a file — see what PII exists (exits 1 if found)
pii-guard scan customers.csv --show-values

# Tokenize — replace PII with tokens, save a session key
pii-guard tokenize customers.csv -p dpdp

# customers.safe.csv now has [EMAIL_1], [AADHAAR_1] etc.
# Analyse it safely with any AI tool.

# Reverse when done
pii-guard detokenize result.txt --session ~/.pii-guard/sessions/pii-guard-<timestamp>.json
```

## Presets

| Preset | Covers |
|--------|--------|
| `dpdp` | 🇮🇳 Aadhaar, PAN, Voter ID, Passport, IFSC, GSTIN, UPI VPA, mobile, PIN code |
| `gdpr` | 🇪🇺 IBAN, BIC/SWIFT, VAT, EU phone, MAC address, GPS coordinates |
| `hipaa`| 🇺🇸 SSN, NPI, DEA, MRN, health plan IDs, US phone, US dates |
| `pci`  | 💳 Visa, Mastercard, Amex, Discover, Rupay, CVV, card expiry |

Use multiple presets at once:

```bash
pii-guard tokenize file.csv -p dpdp -p pci
```

Inspect what patterns a preset uses:

```bash
pii-guard config show-patterns dpdp
```

## Claude Code integration

One command sets everything up:

```bash
pip install pii-guard
pii-guard install-hooks
```

This installs two PostToolUse hooks into `~/.pii-guard/hooks/` and wires them into your project's `.claude/settings.json`. Every file Claude reads and every bash command output is automatically scanned and tokenized before entering the model's context.

Add the behavioral layer (tells Claude to offer tokenization proactively):

```bash
cp integrations/CLAUDE.md .
```

### What the hooks do

```
Claude calls Read("customers.csv")
        ↓
post_read.py intercepts the result
        ↓
Scans for PII → finds 20 instances
        ↓
Replaces with tokens, saves session key to ~/.pii-guard/sessions/claude-<session-id>.json
        ↓
Claude sees [EMAIL_1], [AADHAAR_1] — never the real values
        ↓
pii-guard detokenize result.txt --session ~/.pii-guard/sessions/claude-<session-id>.json
```

All tool calls within one Claude Code session share a single session file, so one detokenize pass restores everything.

### Control via environment variables

```bash
export PII_GUARD_PRESETS=dpdp,pci   # comma-separated presets (default: dpdp)
export PII_GUARD_ENABLED=0          # disable hooks without removing them
export PII_GUARD_MAX_CHARS=200000   # cap bash output scan size (default: 200000)
```

## API Proxy — control point for production apps

If your application calls the Claude or OpenAI API directly, use the proxy to intercept every request before it hits the upstream server.

```bash
pii-guard proxy --port 8111 --preset dpdp
```

Then point your SDK at the proxy with a single env var — no code changes needed:

```bash
# Anthropic SDK
export ANTHROPIC_BASE_URL=http://localhost:8111

# OpenAI-compatible SDK (Codex, GPT, etc.)
export OPENAI_BASE_URL=http://localhost:8111/openai/v1
```

Your existing code works unchanged:

```python
import anthropic

client = anthropic.Anthropic()  # routes through pii-guard automatically

response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Analyse rajesh@gmail.com, Aadhaar 2345 6789 0123"}]
)
# Anthropic receives: "Analyse [EMAIL_1], Aadhaar [AADHAAR_1]"
# Your app receives:  "Analyse rajesh@gmail.com, Aadhaar 2345 6789 0123"
```

### What the proxy does

```
Your app sends prompt with real PII
        ↓
pii-guard proxy intercepts on localhost:8111
        ↓
Tokenizes PII → [EMAIL_1], [AADHAAR_1], [PAN_1]
        ↓
Forwards tokenized prompt to api.anthropic.com
        ↓
Gets response containing tokens
        ↓
Detokenizes response → real values restored
        ↓
Your app receives response with real values
```

Anthropic never sees the real data. Your app never knows the difference.

### Proxy options

```bash
pii-guard proxy --port 8111            # default port
pii-guard proxy --preset dpdp,pci     # multiple presets
pii-guard proxy --pattern "CUST_ID:CUST-\d{6}"  # custom pattern
pii-guard proxy --session session.json # resume existing session
pii-guard proxy --quiet               # suppress per-request logs
```

### Restore real values

The proxy saves a session key for the lifetime of the proxy process:

```bash
# Export as CSV for Excel / VLOOKUP
pii-guard export-session ~/.pii-guard/sessions/<session-id>.json

# Or detokenize an output file
pii-guard detokenize output.txt --session ~/.pii-guard/sessions/<session-id>.json
```

## How tokenization works

Same value → same token within a session. Different values → different tokens. Fully reversible.

```
john@acme.com   →  [EMAIL_1]     (always, within this session)
jane@acme.com   →  [EMAIL_2]
john@acme.com   →  [EMAIL_1]     ← same input, same token
2345 6789 0123  →  [AADHAAR_1]
```

Session key stays in `~/.pii-guard/sessions/`. Never sent anywhere.

## Custom patterns

### Persistent — `~/.pii-guard/config.yaml`

Patterns here are loaded automatically by every CLI command and the Claude Code hooks:

```yaml
custom_patterns:
  CUSTOMER_ID: 'CUST-\d{6}'
  EMPLOYEE_ID: 'EMP\d{5}'
  INTERNAL_REF: 'INT-[A-Z]{3}-\d{4}'
```

Create the file if it doesn't exist — copy the example as a starting point:

```bash
mkdir -p ~/.pii-guard
cp config/pii-guard.example.yaml ~/.pii-guard/config.yaml
```

### Inline — `--pattern` / `-P` flag

For one-off patterns without touching the config file:

```bash
# Scan with a custom pattern
pii-guard scan file.csv -P "CUSTOMER_ID:CUST-\d{6}" --show-values

# Tokenize with multiple custom patterns
pii-guard tokenize file.csv -P "CUSTOMER_ID:CUST-\d{6}" -P "EMPLOYEE_ID:EMP\d{5}"
```

The token name is the key you provide — `CUST-123456` becomes `[CUSTOMER_ID_1]`, fully reversible like any built-in type.

You can combine presets and custom patterns freely:

```bash
pii-guard tokenize data.csv -p dpdp -p pci -P "ACCOUNT_REF:ACC-\d{8}"
```

See `config/pii-guard.example.yaml` for the full config reference.

## Use from Python

```python
from pii_guard.presets import load_presets
from pii_guard.scanner.engine import Scanner
from pii_guard.scanner.patterns import BASE_PATTERNS
from pii_guard.tokenizer.engine import tokenize
from pii_guard.tokenizer.session import Session

patterns = {**BASE_PATTERNS, **load_presets(["dpdp"])}
scanner = Scanner(patterns)
session = Session.new()

safe_text, matches = tokenize(raw_text, scanner, session)
session.save()

print(f"Tokenized {len(matches)} PII instances.")
print(f"Session key: {session.path}")
```

## Contributing

Contributions welcome — especially:

- New preset patterns (country-specific IDs, sector-specific formats)
- False positive reports with reproducible examples
- IDE integrations beyond Claude Code

```bash
git clone https://github.com/pii-guard/pii-guard
cd pii-guard
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest
```

Pattern PRs should include a test in `tests/test_presets.py` that covers at least one valid and one invalid example.

## License

MIT
