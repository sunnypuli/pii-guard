"""
DPDP preset — India-specific PII patterns.

Covers identifiers regulated under:
  - Digital Personal Data Protection Act 2023 (DPDP)
  - Aadhaar (Targeted Delivery of Financial and Other Subsidies) Act 2016
  - Prevention of Money Laundering Act (PMLA) — PAN / bank accounts

All patterns validated against official format specifications.
"""

DPDP_PATTERNS: dict[str, str] = {
    # ── Government IDs ────────────────────────────────────────────────────────

    # Aadhaar: 12-digit number, first digit 2–9
    # Formats: 2345 6789 0123 | 2345-6789-0123 | 234567890123
    "AADHAAR": r"\b[2-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}\b",

    # PAN (Permanent Account Number): AAAAA9999A
    # 5 uppercase letters + 4 digits + 1 uppercase letter
    # (4th char is technically a type code, but scanners should not reject valid PANs
    # from older series or test data — keep broad)
    "PAN": r"\b[A-Z]{5}\d{4}[A-Z]\b",

    # Indian Passport: 1 letter + 7 digits
    # Valid series: A–PR-WY (excluding Q, S, X, Z historically, but keeping broad)
    "PASSPORT_IN": r"\b[A-PR-WY]\d{7}\b",

    # Voter ID (EPIC): 3 uppercase letters + 7 digits
    "VOTER_ID": r"\b[A-Z]{3}\d{7}\b",

    # Driving Licence: state code (2 alpha) + 2-digit year + 7 digits
    # e.g. KA0120230001234
    "DRIVING_LICENCE_IN": r"\b[A-Z]{2}\d{2}\s?\d{4}\s?\d{7}\b",

    # ── Financial identifiers ─────────────────────────────────────────────────

    # IFSC (Indian Financial System Code): AAAA0XXXXXX
    "IFSC": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",

    # GST Identification Number (GSTIN): 15 chars
    # 2-digit state + PAN (10) + Z + check digit
    "GSTIN": r"\b\d{2}[A-Z]{3}[ABCFGHLJPTF][A-Z]\d{4}[A-Z][A-Z\d]Z[A-Z\d]\b",

    # UPI VPA — username@bankhandle
    # Using known bank/PSP handles to reduce false positives vs email
    "UPI_VPA": (
        r"\b[\w.\-]+@("
        r"okaxis|okhdfc|okhdfcbank|okicici|oksbi|paytm|"
        r"ybl|ibl|axl|upi|icici|hdfc|sbi|kotak|axisbank|"
        r"indus|pnb|bob|cnrb|barodampay|aubank|fbl|"
        r"jupiteraxis|naviaxis|slice|niyoaxis|"
        r"phonepe|gpay|amazonpay|airtel"
        r")\b"
    ),

    # Bank account number: 9–18 digits
    # DISABLED by default — extremely high false-positive rate on any numeric data.
    # Enable via custom_patterns in config if needed:
    #   BANK_ACCOUNT_IN: '\b\d{9,18}\b'
    # "BANK_ACCOUNT_IN": r"\b\d{9,18}\b",

    # ── Contact ───────────────────────────────────────────────────────────────

    # Indian mobile: optional +91 or 0 prefix, then 6–9 starting digit + 9 more digits
    # Allows common UI spacing: 98765 43210 or 9876543210
    "MOBILE_IN": r"(?<!\w)(?:\+91[\s\-]?|0)?[6-9]\d{4}[\s\-]?\d{5}\b",

    # Indian PIN code (postal): 6-digit, first digit 1–9
    "PINCODE_IN": r"\b[1-9]\d{5}\b",

    # ── Dates (DOB context) ───────────────────────────────────────────────────

    # DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    "DOB": (
        r"\b(?:0?[1-9]|[12]\d|3[01])"
        r"[/\-\.]"
        r"(?:0?[1-9]|1[0-2])"
        r"[/\-\.]"
        r"(?:19|20)\d{2}\b"
    ),
}
