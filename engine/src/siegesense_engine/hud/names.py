"""Matching player names read by OCR, which often gets one character wrong (0/O, l/1/I)."""

from __future__ import annotations

import re

from rapidfuzz.distance import Levenshtein

NAME_RE = re.compile(r"^[A-Za-z0-9._-]{2,16}$")


def clean_name(text: str) -> str:
    return text.strip().replace(" ", "")


def looks_like_name(text: str) -> bool:
    return bool(NAME_RE.match(clean_name(text)))


def same_name(a: str, b: str) -> bool:
    """One edit allowed for short names (≤ 6 characters), two for longer ones."""
    a, b = clean_name(a).lower(), clean_name(b).lower()
    if not a or not b:
        return False
    allowed = 1 if max(len(a), len(b)) <= 6 else 2
    if abs(len(a) - len(b)) > allowed:
        return False
    return Levenshtein.distance(a, b, score_cutoff=allowed) <= allowed
