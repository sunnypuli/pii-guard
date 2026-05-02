"""
Core scanner engine.

Usage:
    from pii_guard.scanner.engine import Scanner
    from pii_guard.presets.dpdp import DPDP_PATTERNS
    from pii_guard.scanner.patterns import BASE_PATTERNS

    scanner = Scanner({**BASE_PATTERNS, **DPDP_PATTERNS})
    matches = scanner.scan("Call me at +91 98765 43210 or john@acme.com")
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class PiiMatch:
    pii_type: str   # e.g. "EMAIL", "AADHAAR"
    start: int      # character offset (inclusive)
    end: int        # character offset (exclusive)
    value: str      # the raw matched string

    @property
    def span(self) -> int:
        return self.end - self.start


class Scanner:
    def __init__(self, patterns: dict[str, str], flags: int = 0):
        self._compiled: dict[str, re.Pattern] = {
            pii_type: re.compile(pattern, flags)
            for pii_type, pattern in patterns.items()
        }

    # ── Public ────────────────────────────────────────────────────────────────

    def scan(self, text: str) -> list[PiiMatch]:
        """Return all non-overlapping PII matches, longest match wins at each position."""
        raw: list[PiiMatch] = []
        for pii_type, regex in self._compiled.items():
            for m in regex.finditer(text):
                raw.append(PiiMatch(pii_type, m.start(), m.end(), m.group()))
        return _deoverlap(raw)

    def has_pii(self, text: str) -> bool:
        return any(
            regex.search(text)
            for regex in self._compiled.values()
        )

    @property
    def active_types(self) -> list[str]:
        return list(self._compiled.keys())


# ── Helpers ───────────────────────────────────────────────────────────────────

def _deoverlap(matches: list[PiiMatch]) -> list[PiiMatch]:
    """
    Remove overlapping matches.
    Sort by start position; for ties, prefer the longer match.
    Once a match is accepted, any subsequent match whose start falls
    within the accepted match's span is dropped.
    """
    accepted: list[PiiMatch] = []
    prev_end = -1

    for m in sorted(matches, key=lambda x: (x.start, -x.span)):
        if m.start >= prev_end:
            accepted.append(m)
            prev_end = m.end

    return accepted
