"""
Session: the key file that maps [TOKEN_N] ↔ original value.

The session file stays on the user's machine.
It is never sent to any AI service.

File format (JSON):
{
  "created": "2024-01-15T10:30:00",
  "tokens": {
    "[EMAIL_1]": "john@example.com",
    "[AADHAAR_1]": "2345 6789 0123"
  },
  "counters": {
    "EMAIL": 1,
    "AADHAAR": 1
  }
}
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


_DEFAULT_SESSION_DIR = Path.home() / ".piiwall" / "sessions"


class Session:
    def __init__(self, path: Path):
        self.path = path
        self._data: dict = self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text(encoding="utf-8"))
        return {
            "created": datetime.now().isoformat(timespec="seconds"),
            "tokens": {},
            "counters": {},
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Tokenization ──────────────────────────────────────────────────────────

    def get_or_create_token(self, pii_type: str, value: str) -> str:
        """
        Return the consistent token for a given (pii_type, value) pair.
        Creates a new token if this value hasn't been seen before.
        Same value always returns the same token within this session.
        """
        tokens: dict[str, str] = self._data["tokens"]

        # Check if this exact value already has a token
        for token, stored_value in tokens.items():
            if stored_value == value:
                return token

        # Mint a new token
        counters: dict[str, int] = self._data.setdefault("counters", {})
        n = counters.get(pii_type, 0) + 1
        counters[pii_type] = n
        token = f"[{pii_type}_{n}]"
        tokens[token] = value
        return token

    # ── Detokenization ────────────────────────────────────────────────────────

    def detokenize(self, text: str) -> str:
        """Replace all tokens in text with their original values."""
        tokens: dict[str, str] = self._data.get("tokens", {})
        # Sort by token length descending to avoid partial replacement
        for token in sorted(tokens, key=len, reverse=True):
            text = text.replace(token, tokens[token])
        return text

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def token_count(self) -> int:
        return len(self._data.get("tokens", {}))

    @property
    def tokens(self) -> dict[str, str]:
        return dict(self._data.get("tokens", {}))

    def summary_by_type(self) -> dict[str, int]:
        """Return {pii_type: count} for all minted tokens."""
        return dict(self._data.get("counters", {}))

    # ── Factories ─────────────────────────────────────────────────────────────

    @classmethod
    def new(cls, directory: Path | None = None) -> "Session":
        """Create a new session with an auto-generated timestamped file."""
        directory = directory or _DEFAULT_SESSION_DIR
        directory.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = directory / f"piiwall-{ts}.json"
        return cls(path)

    @classmethod
    def load(cls, path: Path | str) -> "Session":
        """Load an existing session from file."""
        return cls(Path(path))
