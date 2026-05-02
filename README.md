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

Add your own PII types in `~/.pii-guard/config.yaml`:

```yaml
custom_patterns:
  CUSTOMER_ID: 'CUST-\d{6}'
  EMPLOYEE_ID: 'EMP\d{5}'
```

Or pass them inline:

```bash
pii-guard scan file.csv --show-values  # with whatever is in config.yaml
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
