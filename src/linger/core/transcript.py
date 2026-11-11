"""Turns a stream of rolling caption snapshots into a stable, duplicate-free transcript.

Windows Live Captions only shows a short, constantly re-written window of text: old lines
scroll away and the newest sentence is revised while it is being spoken.  ``Transcript``
receives every snapshot, commits sentences once they are finished and keeps the
unfinished tail separately as ``partial``.
"""

from __future__ import annotations

import difflib
import time
from collections.abc import Callable
from dataclasses import dataclass

from .text import loose, loose_word, norm, similar, split_sentences

ANCHOR_LOOKBACK = 6     # how many committed sentences we try to find in a new snapshot
SETTLE_SENTENCES = 2    # the newest N sentences may still be revised by the recogniser
DEDUP_WINDOW = 40       # fallback duplicate check when no anchor is found


@dataclass(frozen=True)
class Line:
    time: float   # unix timestamp when the sentence was committed
    text: str


class Transcript:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock
        self.lines: list[Line] = []
        self.partial = ""
        self.version = 0            # bumped on clear() so views know to rebuild
        self._baseline_words: list[str] = []   # normalized words on screen before Start

    # ------------------------------------------------------------------ state
    @property
    def texts(self) -> list[str]:
        return [ln.text for ln in self.lines]

    @property
    def word_count(self) -> int:
        return sum(len(ln.text.split()) for ln in self.lines) + len(self.partial.split())

    def set_baseline(self, text: str) -> None:
        """Ignore text that was already on screen before recording started.

        The old text is located by *position* (where its last words appear in each snapshot),
        not by content, so new speech that happens to repeat old sentences is still recorded."""
        self._baseline_words = loose(text).split()

    def clear(self) -> None:
        self.lines.clear()
        self.partial = ""
        self.version += 1
        self._baseline_words = []

    # ------------------------------------------------------------------ ingest
    def update(self, snapshot: str) -> bool:
        """Feed the current caption text. Returns True if anything visible changed."""
        if self._baseline_words and self.lines:
            self._baseline_words = []            # committed text now anchors new snapshots
        if self._baseline_words:
            trimmed = self._after_baseline(snapshot)
            if trimmed is None:
                self._baseline_words = []        # the old text has scrolled out of view
            else:
                snapshot = trimmed
        parts = split_sentences(snapshot)
        if not parts:
            return False
        # Live Captions often rewrites the last *finished* sentence once the next one starts
        # (e.g. "one point oh" -> "1.0"), so we only commit sentences that have settled.
        final = parts[:-SETTLE_SENTENCES]
        partial = " ".join(parts[-SETTLE_SENTENCES:])
        if not final and self.partial:
            self._commit_scrolled_off(self.partial, partial)
        changed = partial != self.partial
        self.partial = partial

        known = self.texts
        start, anchored = self._find_anchor(final, known)
        recent = known[-DEDUP_WINDOW:]

        for sentence in final[start:]:
            if not anchored and any(similar(sentence, r) or norm(r).endswith(norm(sentence)) for r in recent):
                continue
            if known and similar(known[-1], sentence):
                continue
            if self.lines and similar(self.lines[-1].text, sentence):
                continue
            self._add(sentence)
            changed = True
        return changed

    def flush(self) -> None:
        """Commit the unfinished sentence (called when recording stops)."""
        for sentence in split_sentences(self.partial):
            if not (self.lines and similar(self.lines[-1].text, sentence)):
                self._add(sentence)
        self.partial = ""

    # ------------------------------------------------------------------ export
    def export(self, fmt: str = "text", include_partial: bool = True) -> str:
        """Export as ``text`` (one paragraph), ``timestamps``, ``markdown`` or ``srt``."""
        lines = list(self.lines)
        if include_partial and self.partial:
            lines.append(Line(self._clock(), self.partial))
        if not lines:
            return ""
        if fmt == "text":
            return " ".join(ln.text for ln in lines)
        if fmt == "timestamps":
            return "\n".join(f"[{_hms(ln.time)}] {ln.text}" for ln in lines)
        if fmt == "markdown":
            day = time.strftime("%Y-%m-%d", time.localtime(lines[0].time))
            body = "\n".join(f"- **{_hms(ln.time)}** {ln.text}" for ln in lines)
            return f"# Transcript — {day}\n\n{body}"
        if fmt == "srt":
            return _to_srt(lines)
        raise ValueError(f"unknown export format: {fmt!r}")

    # ------------------------------------------------------------------ internals
    def _add(self, text: str) -> None:
        self.lines.append(Line(self._clock(), text))

    @staticmethod
    def _find_anchor(final: list[str], known: list[str]) -> tuple[int, bool]:
        """Locate the newest already-known sentence inside the snapshot.

        Returns (index of first new sentence, anchor found)."""
        for back in range(1, min(ANCHOR_LOOKBACK, len(known)) + 1):
            anchor = known[-back]
            for i in range(len(final) - 1, -1, -1):
                if similar(final[i], anchor):
                    return i + back, True
        return 0, False

    def _after_baseline(self, snapshot: str) -> str | None:
        """Return only the text that follows the pre-Start text, or None if it is gone.

        The baseline is aligned against the snapshot with difflib on number-insensitive words, so
        it survives Live Captions re-punctuating or re-formatting its history. For ties difflib
        prefers the earliest position — older text is always to the left of new speech."""
        tokens = snapshot.split()
        indexed = [(i, w) for i, w in ((i, loose_word(t)) for i, t in enumerate(tokens)) if w]
        words = [w for _, w in indexed]
        base = self._baseline_words
        if not words:
            return ""
        sm = difflib.SequenceMatcher(None, base, words, autojunk=False)
        blocks = [b for b in sm.get_matching_blocks() if b.size >= 2]
        if not blocks:
            return None
        last = blocks[-1]
        if last.a + last.size < len(base) - 12:
            return None   # only the beginning of the old text matched: it is no longer the tail
        trailing = len(base) - (last.a + last.size)          # old words that were revised away
        return self._rest(tokens, indexed, last.b + last.size - 1 + min(trailing, 2))

    @staticmethod
    def _rest(tokens: list[str], indexed: list[tuple[int, str]], k: int) -> str:
        if k >= len(indexed) - 1:
            return ""
        rest = " ".join(tokens[indexed[k][0] + 1:])
        return rest[:1].upper() + rest[1:]

    def _commit_scrolled_off(self, old: str, new: str) -> None:
        """For long unpunctuated speech: keep the words that scrolled off the top."""
        ow, nw = old.split(), new.split()
        if len(ow) < 6 or norm(" ".join(ow[:4])) in norm(new):
            return
        for k in range(1, len(ow) - 2):
            tail = ow[k:]
            if [norm(w) for w in nw[: len(tail)]] == [norm(w) for w in tail]:
                self._add(" ".join(ow[:k]))
                return


def _hms(t: float) -> str:
    return time.strftime("%H:%M:%S", time.localtime(t))


def _srt_ts(seconds: float) -> str:
    ms = max(0, int(round(seconds * 1000)))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _to_srt(lines: list[Line]) -> str:
    """Commit times are when a sentence *finished*; use the previous one as its start."""
    t0 = lines[0].time - max(1.0, min(6.0, len(lines[0].text.split()) * 0.4))
    out, prev = [], t0
    for i, ln in enumerate(lines, 1):
        start, end = prev - t0, max(ln.time - t0, prev - t0 + 0.5)
        out.append(f"{i}\n{_srt_ts(start)} --> {_srt_ts(end)}\n{ln.text}\n")
        prev = ln.time
    return "\n".join(out)
