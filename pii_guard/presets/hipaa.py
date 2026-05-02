"""
HIPAA preset — US healthcare PII / PHI patterns.

Covers the 18 HIPAA Safe Harbor identifiers where regex-detectable.
"""

HIPAA_PATTERNS: dict[str, str] = {
    # US Social Security Number
    "SSN_US": r"\b(?!000|666|9\d\d)\d{3}[\s\-]?(?!00)\d{2}[\s\-]?(?!0000)\d{4}\b",

    # US phone (NANP)
    "PHONE_US": r"\b(?:\+1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}\b",

    # US ZIP code (5-digit or ZIP+4)
    "ZIP_US": r"\b\d{5}(?:[\-]\d{4})?\b",

    # NPI (National Provider Identifier): 10 digits starting with 1 or 2
    "NPI": r"\b[12]\d{9}\b",

    # DEA number (Drug Enforcement Administration): 2 alpha + 7 digits
    "DEA_NUMBER": r"\b[A-Z]{2}\d{7}\b",

    # Medical Record Number: common formats (heuristic)
    "MRN": r"\bMRN?[\s:\-]{0,2}[A-Z0-9]{6,12}\b",

    # Health plan / member ID: common pattern
    "HEALTH_PLAN_ID": r"\b[A-Z]{3}\d{9}\b",

    # Account / certificate numbers (broad)
    "ACCOUNT_NUM_US": r"\b\d{10,17}\b",

    # Dates (full — YYYY-MM-DD, MM/DD/YYYY)
    "DATE_US": (
        r"\b(?:(?:0?[1-9]|1[0-2])/(?:0?[1-9]|[12]\d|3[01])/(?:19|20)\d{2}"
        r"|(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))\b"
    ),
}
