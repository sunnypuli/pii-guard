"""
Tokenizer engine.

Takes text + a Scanner + a Session and returns the tokenized text.
Works by replacing matches right-to-left so character offsets stay valid.
"""

from __future__ import annotations

from pii_guard.scanner.engine import PiiMatch, Scanner
from pii_guard.tokenizer.session import Session


def tokenize(text: str, scanner: Scanner, session: Session) -> tuple[str, list[PiiMatch]]:
    """
    Scan text for PII and replace each match with its consistent token.

    Returns:
        (tokenized_text, list_of_matches)
    """
    matches = scanner.scan(text)
    if not matches:
        return text, []

    result = list(text)

    # Process right-to-left so earlier offsets remain valid after each replacement
    for match in reversed(matches):
        token = session.get_or_create_token(match.pii_type, match.value)
        result[match.start:match.end] = list(token)

    return "".join(result), matches


def detokenize(text: str, session: Session) -> str:
    """Replace all tokens in text with their original values from the session."""
    return session.detokenize(text)
