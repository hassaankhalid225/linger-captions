"""Small text helpers used to compare caption snapshots."""

from __future__ import annotations

import difflib
import re

# Sentence terminators: Latin + Devanagari danda + Urdu full stop.
_TERMINATORS = ".?!।۔"
# Split on whitespace that follows a terminator (optionally followed by a closing quote/bracket),
# so decimals like "1.0" or "3.5" are never treated as sentence ends.
_SPLIT_RE = re.compile(rf"(?:(?<=[{_TERMINATORS}])|(?<=[{_TERMINATORS}][\"')\]]))\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")

SIMILARITY_THRESHOLD = 0.85


def split_sentences(text: str) -> list[str]:
    """Split text into sentences. The last element may be an unfinished sentence."""
    text = " ".join(text.split())
    return [s for s in _SPLIT_RE.split(text) if s]


def norm(text: str) -> str:
    """Lower-case, strip punctuation and collapse whitespace."""
    return " ".join(_PUNCT_RE.sub("", text.lower()).split())


# Live Captions later rewrites spoken numbers ("three point five" -> "3.5"), so number words and
# digits are ignored when deciding whether two snippets are "the same text".
NUMBER_WORDS = frozenset(
    "zero oh one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred "
    "thousand million billion point percent".split()
)


def loose_word(token: str) -> str:
    """Normalized word, or "" for punctuation, digits and number words."""
    w = norm(token)
    return "" if (not w or w.isdigit() or w in NUMBER_WORDS) else w


def loose(text: str) -> str:
    return " ".join(w for w in map(loose_word, text.split()) if w)


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def similar(a: str, b: str) -> bool:
    """True when two sentences are the same modulo punctuation, number formatting or small ASR revisions."""
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return na == nb
    if na == nb or _ratio(na, nb) > SIMILARITY_THRESHOLD:
        return True
    la, lb = loose(a), loose(b)
    return len(la.split()) >= 2 and len(lb.split()) >= 2 and (la == lb or _ratio(la, lb) > 0.9)
