"""
Base PII patterns included in every preset.
These are universally identifying regardless of jurisdiction.
"""

BASE_PATTERNS: dict[str, str] = {
    # Email — also catches UPI VPAs; UPI preset narrows further
    "EMAIL": r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b",

    # IPv4 — personal identifier under GDPR/DPDP
    "IP_V4": (
        r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
    ),

    # IPv6 full form
    "IP_V6": r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b",

    # Credentials embedded in URLs — https://user:pass@host
    "URL_WITH_CREDS": r"https?://[^:\s/]+:[^@\s/]+@\S+",

    # JWT tokens — header.payload.sig, payload contains user claims
    "JWT": r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b",

    # Generic API keys / secrets — high-entropy hex/base64 strings ≥32 chars
    # Heuristic only; tune via config to reduce false positives
    "API_KEY": r"\b(?:[a-zA-Z0-9_\-]{32,})\b",
}
