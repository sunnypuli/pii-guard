"""Tests for tokenizer engine and session management."""

import json
import tempfile
from pathlib import Path

import pytest

from pii_guard.presets.dpdp import DPDP_PATTERNS
from pii_guard.scanner.engine import Scanner
from pii_guard.scanner.patterns import BASE_PATTERNS
from pii_guard.tokenizer.engine import detokenize, tokenize
from pii_guard.tokenizer.session import Session


@pytest.fixture
def tmp_session(tmp_path):
    return Session(tmp_path / "test-session.json")


@pytest.fixture
def scanner():
    return Scanner({**BASE_PATTERNS, **DPDP_PATTERNS})


class TestSession:
    def test_new_token_created(self, tmp_session):
        token = tmp_session.get_or_create_token("EMAIL", "a@b.com")
        assert token == "[EMAIL_1]"

    def test_same_value_same_token(self, tmp_session):
        t1 = tmp_session.get_or_create_token("EMAIL", "a@b.com")
        t2 = tmp_session.get_or_create_token("EMAIL", "a@b.com")
        assert t1 == t2

    def test_different_values_different_tokens(self, tmp_session):
        t1 = tmp_session.get_or_create_token("EMAIL", "a@b.com")
        t2 = tmp_session.get_or_create_token("EMAIL", "x@y.com")
        assert t1 != t2
        assert t1 == "[EMAIL_1]"
        assert t2 == "[EMAIL_2]"

    def test_counter_per_type(self, tmp_session):
        tmp_session.get_or_create_token("EMAIL", "a@b.com")
        tmp_session.get_or_create_token("AADHAAR", "2345 6789 0123")
        assert tmp_session.summary_by_type() == {"EMAIL": 1, "AADHAAR": 1}

    def test_save_and_reload(self, tmp_path):
        path = tmp_path / "session.json"
        sess = Session(path)
        sess.get_or_create_token("EMAIL", "a@b.com")
        sess.save()

        reloaded = Session(path)
        token = reloaded.get_or_create_token("EMAIL", "a@b.com")
        assert token == "[EMAIL_1]"    # same token after reload

    def test_detokenize(self, tmp_session):
        tmp_session.get_or_create_token("EMAIL", "john@example.com")
        text = "Sending to [EMAIL_1] now"
        result = tmp_session.detokenize(text)
        assert result == "Sending to john@example.com now"


class TestTokenizeEngine:
    def test_basic_round_trip(self, scanner, tmp_session):
        original = "Contact john@example.com or call +91 9876543210"
        tokenized, matches = tokenize(original, scanner, tmp_session)

        assert "john@example.com" not in tokenized
        assert "+91 9876543210" not in tokenized
        assert "[EMAIL_1]" in tokenized
        assert "[MOBILE_IN_1]" in tokenized

        restored = detokenize(tokenized, tmp_session)
        assert restored == original

    def test_no_pii_unchanged(self, scanner, tmp_session):
        text = "This is a clean sentence with no PII."
        tokenized, matches = tokenize(text, scanner, tmp_session)
        assert tokenized == text
        assert matches == []

    def test_repeated_value_same_token(self, scanner, tmp_session):
        text = "Send to john@x.com and CC john@x.com again"
        tokenized, _ = tokenize(text, scanner, tmp_session)
        assert tokenized.count("[EMAIL_1]") == 2
        assert "[EMAIL_2]" not in tokenized

    def test_multiple_pii_types(self, scanner, tmp_session):
        text = "Name: ABCDE1234F, email: a@b.com, aadhaar: 2345 6789 0123"
        tokenized, matches = tokenize(text, scanner, tmp_session)

        types = {m.pii_type for m in matches}
        assert "PAN" in types
        assert "EMAIL" in types
        assert "AADHAAR" in types
