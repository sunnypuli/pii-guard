"""
PCI-DSS preset — payment card industry patterns.
"""

PCI_PATTERNS: dict[str, str] = {
    # Credit / debit card numbers by major network
    # Visa: 4xxx, 16 digits
    "CARD_VISA": r"\b4[0-9]{12}(?:[0-9]{3})?\b",

    # Mastercard: 51–55 or 2221–2720, 16 digits
    "CARD_MASTERCARD": r"\b(?:5[1-5][0-9]{14}|2(?:2[2-9][1-9]|[3-6]\d\d|7[01]\d|720)\d{12})\b",

    # Amex: 34xx or 37xx, 15 digits
    "CARD_AMEX": r"\b3[47][0-9]{13}\b",

    # Discover: 6011, 622126–622925, 644–649, 65, 16 digits
    "CARD_DISCOVER": r"\b(?:6(?:011|5[0-9]{2}))[0-9]{12}\b",

    # Rupay (India): 60, 6521, 6522 prefixes
    "CARD_RUPAY": r"\b(?:60[0-9]{14}|6521[0-9]{12}|6522[0-9]{12})\b",

    # CVV/CVC — 3 or 4 digits near "cvv"/"cvc"/"security code" keyword
    # Pattern alone is too broad; kept for keyword-context scanning
    "CVV": r"(?i)\b(?:cvv|cvc|cvn|security[\s_]?code)[\s:=]{0,3}(\d{3,4})\b",

    # Card expiry: MM/YY or MM/YYYY
    "CARD_EXPIRY": r"\b(?:0[1-9]|1[0-2])/(?:\d{2}|\d{4})\b",
}
