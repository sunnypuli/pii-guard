"""
Tests for GDPR, HIPAA, and PCI preset patterns.

Each test builds a Scanner from only the relevant preset so failures are
isolated to a single pattern type.
"""

from __future__ import annotations

import pytest

from pii_guard.presets.gdpr import GDPR_PATTERNS
from pii_guard.presets.hipaa import HIPAA_PATTERNS
from pii_guard.presets.pci import PCI_PATTERNS
from pii_guard.scanner.engine import Scanner


def _scanner(patterns: dict) -> Scanner:
    return Scanner(patterns)


# ── GDPR ──────────────────────────────────────────────────────────────────────

class TestPhoneEU:
    def setup_method(self):
        self.s = _scanner({"PHONE_EU": GDPR_PATTERNS["PHONE_EU"]})

    def test_netherlands(self):
        assert self.s.has_pii("+31612345678")

    def test_germany(self):
        assert self.s.has_pii("+4917612345678")

    def test_france(self):
        assert self.s.has_pii("+33612345678")

    def test_compact_plus91_not_eu(self):
        # +91 is India — not in the EU country code list
        assert not self.s.has_pii("+919876543210")

    def test_no_plus_not_matched(self):
        assert not self.s.has_pii("0612345678")


class TestIBAN:
    def setup_method(self):
        self.s = _scanner({"IBAN": GDPR_PATTERNS["IBAN"]})

    def test_german_iban(self):
        assert self.s.has_pii("DE89370400440532013000")

    def test_uk_iban(self):
        assert self.s.has_pii("GB29NWBK60161331926819")

    def test_short_not_iban(self):
        assert not self.s.has_pii("DE12")


class TestBICSWIFT:
    def setup_method(self):
        self.s = _scanner({"BIC_SWIFT": GDPR_PATTERNS["BIC_SWIFT"]})

    def test_8char_bic(self):
        assert self.s.has_pii("DEUTDEDB")

    def test_11char_bic(self):
        assert self.s.has_pii("NWBKGB2LXXX")


class TestMACAddress:
    def setup_method(self):
        self.s = _scanner({"MAC_ADDRESS": GDPR_PATTERNS["MAC_ADDRESS"]})

    def test_colon_separated(self):
        assert self.s.has_pii("00:1A:2B:3C:4D:5E")

    def test_hyphen_separated(self):
        assert self.s.has_pii("00-1A-2B-3C-4D-5E")

    def test_lowercase_hex(self):
        assert self.s.has_pii("00:1a:2b:3c:4d:5e")

    def test_short_not_mac(self):
        assert not self.s.has_pii("00:1A:2B:3C")


class TestGeoCoords:
    def setup_method(self):
        self.s = _scanner({"GEO_COORDS": GDPR_PATTERNS["GEO_COORDS"]})

    def test_berlin(self):
        assert self.s.has_pii("52.5200,13.4050")

    def test_with_space(self):
        assert self.s.has_pii("52.5200, 13.4050")

    def test_negative_lat(self):
        assert self.s.has_pii("-33.8688,151.2093")


# ── HIPAA ─────────────────────────────────────────────────────────────────────

class TestSSN:
    def setup_method(self):
        self.s = _scanner({"SSN_US": HIPAA_PATTERNS["SSN_US"]})

    def test_dashed(self):
        assert self.s.has_pii("123-45-6789")

    def test_no_separator(self):
        assert self.s.has_pii("123456789")

    def test_invalid_000_prefix(self):
        assert not self.s.has_pii("000-45-6789")

    def test_invalid_666_prefix(self):
        assert not self.s.has_pii("666-45-6789")

    def test_invalid_900s_prefix(self):
        assert not self.s.has_pii("900-45-6789")


class TestPhoneUS:
    def setup_method(self):
        self.s = _scanner({"PHONE_US": HIPAA_PATTERNS["PHONE_US"]})

    def test_dashed(self):
        assert self.s.has_pii("555-123-4567")

    def test_parenthesised(self):
        assert self.s.has_pii("(555) 123-4567")

    def test_country_code(self):
        assert self.s.has_pii("+1 555 123 4567")


class TestNPI:
    def setup_method(self):
        self.s = _scanner({"NPI": HIPAA_PATTERNS["NPI"]})

    def test_valid_npi(self):
        assert self.s.has_pii("1234567890")

    def test_starts_with_3_not_npi(self):
        assert not self.s.has_pii("3234567890")


class TestDEANumber:
    def setup_method(self):
        self.s = _scanner({"DEA_NUMBER": HIPAA_PATTERNS["DEA_NUMBER"]})

    def test_valid_dea(self):
        assert self.s.has_pii("AB1234567")

    def test_too_short(self):
        assert not self.s.has_pii("AB123456")


class TestMRN:
    def setup_method(self):
        self.s = _scanner({"MRN": HIPAA_PATTERNS["MRN"]})

    def test_with_colon(self):
        assert self.s.has_pii("MRN: A1234567")

    def test_with_dash(self):
        assert self.s.has_pii("MRN-B9876543")

    def test_no_separator(self):
        assert self.s.has_pii("MRN123456")


class TestDateUS:
    def setup_method(self):
        self.s = _scanner({"DATE_US": HIPAA_PATTERNS["DATE_US"]})

    def test_mm_dd_yyyy(self):
        assert self.s.has_pii("01/15/2024")

    def test_iso_format(self):
        assert self.s.has_pii("2024-01-15")

    def test_invalid_month_13(self):
        assert not self.s.has_pii("13/15/2024")


# ── PCI ───────────────────────────────────────────────────────────────────────

class TestCardVisa:
    def setup_method(self):
        self.s = _scanner({"CARD_VISA": PCI_PATTERNS["CARD_VISA"]})

    def test_16_digit(self):
        assert self.s.has_pii("4111111111111111")

    def test_13_digit(self):
        assert self.s.has_pii("4111111111111")

    def test_not_visa(self):
        assert not self.s.has_pii("5111111111111111")


class TestCardMastercard:
    def setup_method(self):
        self.s = _scanner({"CARD_MASTERCARD": PCI_PATTERNS["CARD_MASTERCARD"]})

    def test_5x_prefix(self):
        assert self.s.has_pii("5500005555555559")

    def test_2xxx_prefix(self):
        assert self.s.has_pii("2221000000000000")


class TestCardAmex:
    def setup_method(self):
        self.s = _scanner({"CARD_AMEX": PCI_PATTERNS["CARD_AMEX"]})

    def test_34_prefix(self):
        assert self.s.has_pii("341111111111111")

    def test_37_prefix(self):
        assert self.s.has_pii("371449635398431")

    def test_not_amex(self):
        assert not self.s.has_pii("351111111111111")


class TestCVV:
    def setup_method(self):
        self.s = _scanner({"CVV": PCI_PATTERNS["CVV"]})

    def test_cvv_colon(self):
        assert self.s.has_pii("CVV: 123")

    def test_lowercase(self):
        assert self.s.has_pii("cvv: 456")

    def test_4digit_amex(self):
        assert self.s.has_pii("CVV: 1234")

    def test_bare_digits_not_cvv(self):
        assert not self.s.has_pii("123")


class TestCardExpiry:
    def setup_method(self):
        self.s = _scanner({"CARD_EXPIRY": PCI_PATTERNS["CARD_EXPIRY"]})

    def test_mm_yy(self):
        assert self.s.has_pii("12/25")

    def test_mm_yyyy(self):
        assert self.s.has_pii("12/2025")

    def test_invalid_month(self):
        assert not self.s.has_pii("13/25")
