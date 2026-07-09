"""Deterministic output validation (FR-3.5, DESIGN §5).

Every reply passes here before it is spoken — the model is never trusted to
skip this guardrail (DESIGN §1.4). The retry-with-corrective-suffix policy
lives in the orchestrator so lexicon substitution can happen between
generation and validation.
"""

from __future__ import annotations

_DEVANAGARI = (0x0900, 0x097F)

MAX_REPLY_CHARS = 220
MIN_DEVANAGARI_RATIO = 0.8


def devanagari_ratio(text: str) -> float:
    """Devanagari codepoints / all script codepoints (letters + combining marks).

    Whitespace, digits, and punctuation are ignored so danda and spaces don't
    dilute the ratio.
    """
    devanagari = 0
    other = 0
    for ch in text:
        if _DEVANAGARI[0] <= ord(ch) <= _DEVANAGARI[1]:
            devanagari += 1
        elif ch.isalpha():
            other += 1
    total = devanagari + other
    return devanagari / total if total else 0.0


def validate(text: str, max_chars: int = MAX_REPLY_CHARS,
             min_ratio: float = MIN_DEVANAGARI_RATIO) -> tuple[bool, str]:
    """Returns (ok, reason). Reason is "" when ok."""
    if not text or not text.strip():
        return False, "empty"
    if len(text) > max_chars:
        return False, f"too long ({len(text)} > {max_chars} chars)"
    ratio = devanagari_ratio(text)
    if ratio < min_ratio:
        return False, f"not Devanagari-dominant (ratio {ratio:.2f} < {min_ratio})"
    return True, ""
