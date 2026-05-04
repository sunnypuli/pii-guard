# pii-guard

**Local PII firewall for AI CLI tools. Tokenize before it leaves your machine.**

When you ask Claude Code or Codex to analyse data, raw PII — Aadhaar numbers, emails, PANs, phone numbers — travels to Anthropic/OpenAI servers. pii-guard intercepts it first, replaces real values with consistent tokens (`[AADHAAR_1]`, `[EMAIL_2]`), and lets the analysis run on the safe version. You keep the key file; you can reverse it any time.

---

## How it works — three modes

```
┌─────────────────────────────────────────────────────────────────────┐
│  Mode 1 · CLI (manual)                                              │
│  You run: pii-guard tokenize file.csv                               │
│  → safe file created → AI analyses safe file → you detokenize       │
├─────────────────────────────────────────────────────────────────────┤
│  Mode 2 · Claude Code hooks (automatic)                             │
│  Claude reads a file → post_read.py intercepts the content          │
│  → PII replaced with tokens before Claude ever sees it              │
│  → same session key, one detokenize pass restores everything        │
├─────────────────────────────────────────────────────────────────────┤
│  Mode 3 · API proxy (production apps)                               │
│  Your app → localhost:8111 → pii-guard tokenizes → api.anthropic.com│
│  Response: detokenized before your app receives it                  │
│  → drop-in: one env var, zero code changes                          │
└─────────────────────────────────────────────────────────────────────┘
```

All three modes use the same tokenization engine and session format. Tokens are consistent across modes within a session: `john@acme.com` is always `[EMAIL_1]`.

---

## Install

```bash
pip install pii-guard
```

---

## Mode 1 — CLI (manual workflow)

### Quickstart

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

### Export session as CSV (for Excel / VLOOKUP)

After tokenizing, export the full mapping as a spreadsheet-friendly CSV:

```bash
pii-guard export-session ~/.pii-guard/sessions/pii-guard-<timestamp>.json
```

Output (`pii-guard-<timestamp>_mapping.csv`):

```
token,pii_type,original_value
[EMAIL_1],EMAIL,john@acme.com
[EMAIL_2],EMAIL,jane@acme.com
[AADHAAR_1],AADHAAR,2345 6789 0123
[PAN_1],PAN,ABCDE1234F
```

Use this for VLOOKUP-based re-identification in Excel or Google Sheets without running the CLI again.

### Presets

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

---

## Mode 2 — Claude Code hooks (automatic, zero-touch)

One command sets everything up:

```bash
pip install pii-guard
pii-guard install-hooks --global
```

This installs two PostToolUse hooks into `~/.pii-guard/hooks/` and wires them into `~/.claude/settings.json`. Every file Claude reads and every bash command output is automatically scanned and tokenized before entering the model's context. No manual steps needed per project.

Add the behavioral layer (tells Claude to offer tokenization proactively):

```bash
cp integrations/CLAUDE.md ~/.claude/CLAUDE.md
```

### What the hooks do

```
Claude calls Read("customers.csv")
        ↓
post_read.py intercepts the tool response
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

### Restore real values after Claude analysis

```bash
pii-guard detokenize result.txt --session ~/.pii-guard/sessions/claude-<session-id>.json
```

Or export the full mapping for the session:

```bash
pii-guard export-session ~/.pii-guard/sessions/claude-<session-id>.json
```

### Control via environment variables

```bash
export PII_GUARD_PRESETS=dpdp,pci   # comma-separated presets (default: dpdp)
export PII_GUARD_ENABLED=0          # disable hooks without removing them
export PII_GUARD_MAX_CHARS=200000   # cap bash output scan size (default: 200000)
```

---

## Mode 3 — API proxy (production apps)

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

### Restore real values from a proxy session

The proxy saves a session key for the lifetime of the proxy process:

```bash
# Export as CSV for Excel / VLOOKUP
pii-guard export-session ~/.pii-guard/sessions/<session-id>.json

# Or detokenize an output file
pii-guard detokenize output.txt --session ~/.pii-guard/sessions/<session-id>.json
```

---

## Custom patterns

### Persistent — `~/.pii-guard/config.yaml`

Patterns here are loaded automatically by every CLI command, the Claude Code hooks, and the proxy:

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

---

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

---

## How tokenization works

Same value → same token within a session. Different values → different tokens. Fully reversible.

```
john@acme.com   →  [EMAIL_1]     (always, within this session)
jane@acme.com   →  [EMAIL_2]
john@acme.com   →  [EMAIL_1]     ← same input, same token
2345 6789 0123  →  [AADHAAR_1]
```

Session key stays in `~/.pii-guard/sessions/`. Never sent anywhere.

---

## Limitations

- **Regex-based detection** — structured formats (Aadhaar, PAN, IBAN, SSN) have near-zero false negatives. Free-form PII (full names, addresses in prose) is not detected; combine with a dedicated NER model if you need it.
- **Same-session tokens only** — tokens from one session cannot be detokenized with a different session key. Keep the session file for as long as you need to reverse the data.
- **Streaming responses** — the proxy detokenizes SSE streams line-by-line. If a token spans two SSE chunks it will not be restored; this is rare but possible with very large token strings.
- **Proxy is localhost-only** — `pii-guard proxy` binds to `127.0.0.1` by default. It is not designed to be exposed to a network; treat the session key file as a secret.
- **No key management** — session files are plain JSON on disk. Encrypt or delete them when no longer needed.

---

## Contributing

Contributions welcome — especially:

- New preset patterns (country-specific IDs, sector-specific formats)
- False positive reports with reproducible examples
- IDE integrations beyond Claude Code

```bash
git clone https://github.com/sunnypuli/pii-guard
cd pii-guard
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest
```

Pattern PRs should include a test in `tests/test_presets.py` that covers at least one valid and one invalid example.

---

## License

MIT
