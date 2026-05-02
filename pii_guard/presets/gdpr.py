"""
GDPR preset — EU/EEA personal data patterns.

Covers common identifiers regulated under GDPR Article 4.
"""

GDPR_PATTERNS: dict[str, str] = {
    # EU phone (international format)
    # Matches ITU-T zones 3–4 (+30…+49), which cover the EU/EEA/candidate countries.
    # (?<!\w) instead of \b because + is a non-word char — \b fails before +
    "PHONE_EU": r"(?<!\w)\+(?:3[0-9]|4[0-9])\d{5,13}\b",

    # EU National ID / SSN (generic numeric, 8–12 digits)
    # DISABLED by default — extremely high false-positive rate on any plain numeric data.
    # Enable via custom_patterns if your data is specifically National ID fields.
    # "NATIONAL_ID_EU": r"\b\d{8,12}\b",

    # IBAN (International Bank Account Number)
    "IBAN": r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b",

    # BIC / SWIFT code
    "BIC_SWIFT": r"\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b",

    # EU VAT number (generic: 2-letter country + 8–12 alphanumeric)
    "VAT_EU": r"\b[A-Z]{2}[A-Z0-9]{8,12}\b",

    # Location coordinates
    "GEO_COORDS": (
        r"\b[-+]?(?:[1-8]?\d(?:\.\d+)?|90(?:\.0+)?)"
        r",\s*[-+]?(?:180(?:\.0+)?|(?:1[0-7]\d|[1-9]?\d)(?:\.\d+)?)\b"
    ),

    # MAC address
    "MAC_ADDRESS": r"\b(?:[0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}\b",
}
