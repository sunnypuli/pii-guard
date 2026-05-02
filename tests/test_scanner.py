"""Tests for the scanner engine + DPDP preset."""

import pytest

from pii_guard.presets.dpdp import DPDP_PATTERNS
from pii_guard.scanner.engine import Scanner, _deoverlap, PiiMatch
from pii_guard.scanner.patterns import BASE_PATTERNS


@pytest.fixture
def dpdp_scanner():
    return Scanner({**BASE_PATTERNS, **DPDP_PATTERNS})


# ── BASE patterns ─────────────────────────────────────────────────────────────

class TestEmail:
    def test_simple(self, dpdp_scanner):
        m = dpdp_scanner.scan("Contact john@example.com for help")
        assert any(m.pii_type == "EMAIL" and m.value == "john@example.com" for m in m)

    def test_not_matched_partial(self, dpdp_scanner):
        matches = dpdp_scanner.scan("not an email @mention")
        emails = [m for m in matches if m.pii_type == "EMAIL"]
        assert not emails


class TestJWT:
    def test_detects_jwt(self, dpdp_scanner):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        matches = dpdp_scanner.scan(f"token={jwt}")
        assert any(m.pii_type == "JWT" for m in matches)


# ── DPDP patterns ─────────────────────────────────────────────────────────────

class TestAadhaar:
    valid = [
        "2345 6789 0123",
        "2345-6789-0123",
        "234567890123",
    ]
    invalid = [
        "1234 5678 9012",   # first digit = 1, invalid
        "0000 0000 0000",
        "1234567",          # too short
    ]

    def test_valid(self, dpdp_scanner):
        for val in self.valid:
            matches = dpdp_scanner.scan(f"aadhaar: {val}")
            assert any(m.pii_type == "AADHAAR" for m in matches), f"Should match: {val}"

    def test_invalid(self, dpdp_scanner):
        for val in self.invalid:
            matches = dpdp_scanner.scan(f"number: {val}")
            aadhaar = [m for m in matches if m.pii_type == "AADHAAR"]
            assert not aadhaar, f"Should NOT match: {val}"


class TestPAN:
    def test_valid(self, dpdp_scanner):
        matches = dpdp_scanner.scan("PAN: ABCDE1234F")
        assert any(m.pii_type == "PAN" and m.value == "ABCDE1234F" for m in matches)

    def test_lowercase_not_matched(self, dpdp_scanner):
        matches = dpdp_scanner.scan("abcde1234f")
        pan = [m for m in matches if m.pii_type == "PAN"]
        assert not pan


class TestMobileIN:
    valid = ["+91 98765 43210", "9876543210", "09876543210", "+919876543210"]

    def test_valid(self, dpdp_scanner):
        for val in self.valid:
            matches = dpdp_scanner.scan(f"mobile: {val}")
            assert any(m.pii_type == "MOBILE_IN" for m in matches), f"Should match: {val}"


class TestIFSC:
    def test_valid(self, dpdp_scanner):
        matches = dpdp_scanner.scan("IFSC: SBIN0001234")
        assert any(m.pii_type == "IFSC" for m in matches)


class TestUPIVPA:
    def test_known_handle(self, dpdp_scanner):
        matches = dpdp_scanner.scan("pay to user@okaxis")
        assert any(m.pii_type == "UPI_VPA" for m in matches)

    def test_regular_email_not_upi(self, dpdp_scanner):
        matches = dpdp_scanner.scan("email: user@gmail.com")
        upi = [m for m in matches if m.pii_type == "UPI_VPA"]
        assert not upi


# ── Deoverlap ─────────────────────────────────────────────────────────────────

class TestDeoverlap:
    def test_longer_wins(self):
        matches = [
            PiiMatch("SHORT", 0, 5, "12345"),
            PiiMatch("LONG",  0, 10, "1234567890"),
        ]
        result = _deoverlap(matches)
        assert len(result) == 1
        assert result[0].pii_type == "LONG"

    def test_non_overlapping_both_kept(self):
        matches = [
            PiiMatch("A", 0, 5, "hello"),
            PiiMatch("B", 10, 15, "world"),
        ]
        result = _deoverlap(matches)
        assert len(result) == 2
