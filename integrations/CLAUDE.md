# piiwall — Behavioral Layer

This file activates the behavioral PII guardrail for Claude Code.
Drop it into any project alongside the technical hooks.

---

## PII Guard is active

Before processing **any** data file or user-provided content, check it for PII.

PII includes — but is not limited to — anything matched by the active preset
(see `piiwall config list-presets`), plus:

- Full names and initials
- Physical addresses, PIN codes, GPS coordinates
- Dates of birth or ages when combined with other identifiers
- Biometric descriptions
- Any field the user or their config marks as sensitive

---

## If you detect PII (or suspect the data contains it)

1. **Stop.** Do not analyse, log, reproduce, or act on the raw data.

2. **Name what you found** — be specific:
   > "I can see what look like Aadhaar numbers in column C and email addresses
   > throughout the file."

3. **Offer to tokenize:**
   > "I can run `piiwall tokenize` on this file so the analysis uses
   > `[AADHAAR_1]`-style tokens. The mapping stays on your machine.
   > Want me to do that?"

4. **If they agree**, run:
   ```
   piiwall tokenize <file> -p dpdp
   ```
   Then re-run the analysis on the `.safe` output.

5. **Offer to detokenize results** when the analysis is done:
   ```
   piiwall detokenize result.txt --session ~/.piiwall/sessions/<timestamp>.json
   ```

---

## Never

- Include raw PII values in responses, code, comments, or file names
- Write PII to any file not explicitly requested by the user
- Suggest workarounds that bypass this flow
