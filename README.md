# piiwall  *(pronounced: Pi-Wall)*

**Local PII firewall for AI coding tools. Tokenize before it leaves your machine.**

When you ask any AI tool — Claude Code, Cursor, Aider, Codex, Continue.dev — to analyse data, raw PII travels to their servers. piiwall intercepts it first: replaces real values with consistent tokens (`[AADHAAR_1]`, `[EMAIL_2]`), lets the AI work on the safe version, and reverses it when you're done. The mapping key never leaves your machine.

---

## Works with every AI tool

| Tool | How |
|------|-----|
| **Claude Code** | PostToolUse hooks — automatic, zero-touch per file read |
| **Cursor** | Set `OPENAI_BASE_URL=http://localhost:8111/openai/v1` |
| **Aider** | Set `OPENAI_API_BASE=http://localhost:8111/openai/v1` |
| **OpenAI Codex CLI** | Set `OPENAI_BASE_URL=http://localhost:8111/openai/v1` |
| **Continue.dev** | Set `apiBase` in `~/.continue/config.json` |
| **Any OpenAI-SDK app** | Set `OPENAI_BASE_URL` — no code changes |
| **Any Anthropic-SDK app** | Set `ANTHROPIC_BASE_URL` — no code changes |
| **Any tool, any LLM** | Manually: `piiwall tokenize file.csv` before sharing |

Integration guides: [`integrations/`](integrations/)

---

## How it works — three modes

```
┌─────────────────────────────────────────────────────────────────────┐
│  Mode 1 · CLI  (any tool, manual)                                   │
│  piiwall tokenize file.csv → safe file → AI analyses → detokenize │
├─────────────────────────────────────────────────────────────────────┤
│  Mode 2 · Claude Code hooks  (automatic, zero-touch)                │
│  piiwall install-hooks → hooks fire on every Read + Bash output   │
│  Claude never sees raw PII in the session                           │
├─────────────────────────────────────────────────────────────────────┤
│  Mode 3 · API proxy  (any OpenAI/Anthropic-compatible tool)         │
│  piiwall proxy → sits between your tool and the upstream API      │
│  One env var. Zero code changes. Works with Cursor, Aider, Codex,  │
│  Continue.dev, LangChain, and any SDK that respects base URL vars.  │
└─────────────────────────────────────────────────────────────────────┘
```

All three modes use the same tokenization engine and session format. `john@acme.com` is always `[EMAIL_1]` within a session, regardless of which mode captured it.

---

## Install

```bash
pip install piiwall            # core (plain text, CSV)
pip install 'piiwall[rich]'    # + PDF, Word (.docx), Excel (.xlsx)
```

---

## Mode 1 — CLI (tool-agnostic, manual)

Works with any AI tool. Tokenize a file first, share the safe version, detokenize results when done.

```bash
# Scan — see what PII exists (exits 1 if found)
piiwall scan customers.csv --show-values

# Tokenize — create customers.safe.csv with tokens
piiwall tokenize customers.csv -p dpdp

# Analyse customers.safe.csv with whatever AI tool you use
# Then restore real values
piiwall detokenize result.txt --session ~/.piiwall/sessions/piiwall-<timestamp>.json
```

### Supported file formats

| Format | Scan | Tokenize | Notes |
|--------|------|----------|-------|
| Plain text, CSV, JSON | ✓ | ✓ | Core, no extra deps |
| PDF (`.pdf`) | ✓ | ✓ | Output as `.safe.txt`; requires `piiwall[rich]` |
| Word (`.docx`) | ✓ | ✓ | Format preserved, paragraphs and tables tokenized in-place; requires `piiwall[rich]` |
| Excel (`.xlsx`) | ✓ | ✓ | Format preserved, all string cells tokenized in-place; requires `piiwall[rich]` |

```bash
pip install 'piiwall[rich]'                 # install format support
piiwall scan report.docx -p dpdp            # scan a Word doc
piiwall tokenize customer_data.xlsx -p dpdp # tokenize an Excel sheet → customer_data.safe.xlsx
piiwall scan employees.pdf -p hipaa         # scan a PDF
```

### Session stats

```bash
piiwall stats ~/.piiwall/sessions/piiwall-<timestamp>.json
```

```
Session:  piiwall-20240115-103000.json
Total tokens: 12

  Type                    Count
  ---------------------- ------
  EMAIL                       4
  AADHAAR                     3
  MOBILE_IN                   3
  PAN                         2
```

### Export session as CSV (for Excel / VLOOKUP)

```bash
piiwall export-session ~/.piiwall/sessions/piiwall-<timestamp>.json
```

Output (`piiwall-<timestamp>_mapping.csv`):

```
token,pii_type,original_value
[EMAIL_1],EMAIL,john@acme.com
[EMAIL_2],EMAIL,jane@acme.com
[AADHAAR_1],AADHAAR,2345 6789 0123
[PAN_1],PAN,ABCDE1234F
```

### Presets

| Preset | Covers |
|--------|--------|
| `dpdp` | 🇮🇳 Aadhaar, PAN, Voter ID, Passport, IFSC, GSTIN, UPI VPA, mobile, PIN code |
| `gdpr` | 🇪🇺 IBAN, BIC/SWIFT, VAT, EU phone, MAC address, GPS coordinates |
| `hipaa`| 🇺🇸 SSN, NPI, DEA, MRN, health plan IDs, US phone, US dates |
| `pci`  | 💳 Visa, Mastercard, Amex, Discover, Rupay, CVV, card expiry |

```bash
piiwall tokenize file.csv -p dpdp -p pci   # combine presets
piiwall config show-patterns dpdp           # inspect patterns in a preset
```

---

## Mode 2 — Claude Code hooks (automatic, zero-touch)

One command installs hooks that fire on every file Claude reads and every bash command output:

```bash
pip install piiwall
piiwall install-hooks --global
```

This writes two PostToolUse hooks into `~/.claude/settings.json`. Claude never sees raw PII in any session.

Add the behavioral layer (tells Claude to proactively offer tokenization):

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
Replaces with tokens, saves session key → ~/.piiwall/sessions/claude-<session-id>.json
        ↓
Claude sees [EMAIL_1], [AADHAAR_1] — never the real values
```

All Read and Bash calls in one Claude Code session share one session file. One detokenize pass restores everything.

### Restore after Claude session

```bash
piiwall detokenize result.txt --session ~/.piiwall/sessions/claude-<session-id>.json
# or export as CSV
piiwall export-session ~/.piiwall/sessions/claude-<session-id>.json
```

### Control via environment variables

```bash
export PIIWALL_PRESETS=dpdp,pci   # comma-separated presets (default: dpdp)
export PIIWALL_ENABLED=0          # disable hooks without removing them
export PIIWALL_MAX_CHARS=200000   # cap bash output scan size (default: 200000)
```

---

## Mode 3 — API proxy (Cursor, Aider, Codex, Continue.dev, any SDK)

The proxy sits between your tool and the upstream API. It tokenizes every outgoing prompt and detokenizes every response. Your tool and your code are unchanged.

```bash
piiwall proxy --port 8111 --preset dpdp
```

### Set the base URL in your tool

```bash
# Anthropic SDK / Claude Code / any Anthropic-compatible tool
export ANTHROPIC_BASE_URL=http://localhost:8111

# OpenAI SDK / Cursor / Aider / Codex CLI / Continue.dev / LangChain
export OPENAI_BASE_URL=http://localhost:8111/openai/v1
```

Your existing code works unchanged:

```python
import anthropic
client = anthropic.Anthropic()   # routes through piiwall automatically

response = client.messages.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Analyse rajesh@gmail.com, Aadhaar 2345 6789 0123"}]
)
# Anthropic receives: "Analyse [EMAIL_1], Aadhaar [AADHAAR_1]"
# Your app receives:  "Analyse rajesh@gmail.com, Aadhaar 2345 6789 0123"
```

### What the proxy does

```
Your tool sends prompt with real PII
        ↓
piiwall proxy on localhost:8111
        ↓
Tokenizes PII → [EMAIL_1], [AADHAAR_1], [PAN_1]
        ↓
Forwards to api.anthropic.com or api.openai.com
        ↓
Gets response with tokens
        ↓
Detokenizes → real values restored
        ↓
Your tool receives response with real values
```

Anthropic and OpenAI never see the real data.

### Proxy options

```bash
piiwall proxy --port 8111                        # default port
piiwall proxy --preset dpdp,pci                  # multiple presets
piiwall proxy --pattern "CUST_ID:CUST-\d{6}"    # custom pattern
piiwall proxy --session session.json             # resume existing session
piiwall proxy --quiet                            # suppress per-request logs
```

### Restore after proxy session

```bash
piiwall export-session ~/.piiwall/sessions/<session-id>.json
piiwall detokenize output.txt --session ~/.piiwall/sessions/<session-id>.json
```

### Per-tool guides

- [Cursor](integrations/cursor/README.md)
- [Aider](integrations/aider/README.md)
- [OpenAI Codex CLI](integrations/codex/README.md)
- [Continue.dev](integrations/continue-dev/README.md)
- [Claude Code hooks](integrations/claude-code/)

---

## Custom patterns

### Persistent — `~/.piiwall/config.yaml`

Loaded automatically by the CLI, hooks, and proxy:

```yaml
custom_patterns:
  CUSTOMER_ID: 'CUST-\d{6}'
  EMPLOYEE_ID: 'EMP\d{5}'
  INTERNAL_REF: 'INT-[A-Z]{3}-\d{4}'
```

```bash
mkdir -p ~/.piiwall
cp config/piiwall.example.yaml ~/.piiwall/config.yaml
```

### Inline — `--pattern` / `-P` flag

```bash
piiwall scan file.csv -P "CUSTOMER_ID:CUST-\d{6}" --show-values
piiwall tokenize file.csv -P "CUSTOMER_ID:CUST-\d{6}" -P "EMPLOYEE_ID:EMP\d{5}"
piiwall tokenize data.csv -p dpdp -p pci -P "ACCOUNT_REF:ACC-\d{8}"
```

`CUST-123456` becomes `[CUSTOMER_ID_1]`, fully reversible.

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

Session key stays in `~/.piiwall/sessions/`. Never sent anywhere.

---

## Limitations

- **Regex-based detection** — structured formats (Aadhaar, PAN, IBAN, SSN) have near-zero false negatives. Free-form PII (names, addresses in prose) is not detected; combine with a dedicated NER model if needed.
- **DOCX formatting in PII-containing paragraphs** — when a PII value spans multiple runs in a Word document (e.g., bold text adjacent to the value), the paragraph is collapsed to a single run after tokenization. Paragraphs with no PII are untouched.
- **Same-session tokens only** — tokens from one session cannot be detokenized with a different session key. Keep the session file for as long as you need to reverse.
- **Streaming responses** — the proxy detokenizes SSE streams line-by-line. A token that spans two SSE chunks will not be restored; rare but possible with large token strings.
- **Proxy is localhost-only** — binds to `127.0.0.1`. Not designed to be network-exposed. Treat the session key file as a secret.
- **No key management** — session files are plain JSON on disk. Encrypt or delete when no longer needed.

---

## CI/CD integration

### GitHub Actions

Copy `integrations/github-actions/pii-scan.yml` into `.github/workflows/` to fail PRs that introduce raw PII in CSV, JSON, TXT, or log files:

```bash
cp integrations/github-actions/pii-scan.yml .github/workflows/pii-scan.yml
```

### pre-commit hook

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/sunnypuli/piiwall
    rev: main
    hooks:
      - id: piiwall-scan
        args: [--preset, dpdp]
```

Then install hooks with `pre-commit install`. Commits that include files with detectable PII will be blocked.

### Audit log

Every `scan` and `tokenize` run appends a line to `~/.piiwall/audit.log`:

```
2024-01-15T10:30:00  tokenize     customers.csv                   total=12  AADHAAR:3 EMAIL:4 PAN:2
```

---

## Docker (proxy)

```bash
docker build -t piiwall .
docker run -p 8111:8111 piiwall --preset dpdp,pci
```

Then set `ANTHROPIC_BASE_URL=http://localhost:8111` or `OPENAI_BASE_URL=http://localhost:8111/openai/v1`.

---

## Contributing

Contributions welcome — especially:

- New preset patterns (country-specific IDs, sector-specific formats)
- False positive reports with reproducible examples
- IDE and tool integrations

```bash
git clone https://github.com/sunnypuli/piiwall
cd piiwall
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest
```

Pattern PRs should include a test in `tests/test_presets.py` covering at least one valid and one invalid example.

---

## License

MIT
