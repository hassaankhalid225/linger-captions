"""Background recording loop: polls a caption source and feeds the transcript."""

from __future__ import annotations

import contextlib
import logging
import os
import threading
import time
from contextlib import AbstractContextManager
from datetime import datetime
from enum import Enum
from typing import Protocol

from .transcript import Transcript

log = logging.getLogger(__name__)


class CaptionSource(Protocol):
    """Anything that can provide the current caption text (see win.live_captions)."""

    def thread_context(self) -> AbstractContextManager: ...
    def ensure_running(self) -> bool: ...
    def hide(self) -> None: ...
    def keep_hidden(self) -> None: ...
    def is_hung(self) -> bool: ...
    def read(self) -> str | None: ...
    def restore(self) -> None: ...


class Status(str, Enum):
    IDLE = "idle"
    STARTING = "starting"
    LISTENING = "listening"
    RECONNECTING = "reconnecting"
    PAUSED = "paused"
    UNAVAILABLE = "unavailable"   # Live Captions could not be started


class Recorder:
    POLL_SECONDS = 0.35
    HUNG_RESTART_TICKS = 12       # ~4 s of an unresponsive Live Captions -> restart it
    MISSING_RECONNECT_TICKS = 4
    AUTOSAVE_SECONDS = 3.0

    def __init__(self, source: CaptionSource, autosave_dir: str | None = None):
        self.source = source
        self.transcript = Transcript()
        self.lock = threading.RLock()
        self.autosave_dir = autosave_dir
        self.status = Status.IDLE
        self._running = threading.Event()
        self._thread: threading.Thread | None = None
        self._started_at: float | None = None
        self._elapsed_before = 0.0
        self._session_file: str | None = None
        self._saved_count = -1
        self._last_autosave = 0.0

    # ------------------------------------------------------------------ control
    @property
    def running(self) -> bool:
        return self._running.is_set()

    def start(self) -> None:
        if self.running:
            return
        if self._thread and self._thread.is_alive():   # previous loop still finishing its sleep
            self._thread.join(timeout=2)
        self._running.set()
        self._started_at = time.time()
        self.status = Status.STARTING
        self._thread = threading.Thread(target=self._run, name="caption-recorder", daemon=True)
        self._thread.start()
        log.info("recording started")

    def stop(self) -> None:
        if not self.running:
            return
        self._running.clear()
        self._elapsed_before += time.time() - (self._started_at or time.time())
        self._started_at = None
        with self.lock:
            self.transcript.flush()
        self.status = Status.PAUSED
        self.autosave(force=True)
        log.info("recording paused (%d lines)", len(self.transcript.lines))

    def clear(self) -> None:
        with self.lock:
            self.transcript.clear()
            self._saved_count = -1
        self._session_file = None
        self._elapsed_before = 0.0
        if self.running:
            self._started_at = time.time()

    def elapsed(self) -> int:
        live = time.time() - self._started_at if self._started_at else 0.0
        return int(self._elapsed_before + live)

    def shutdown(self) -> None:
        self._running.clear()
        self.autosave(force=True)
        with contextlib.suppress(Exception):
            self.source.restore()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    @property
    def session_file(self) -> str | None:
        return self._session_file

    # ------------------------------------------------------------------ worker
    def _run(self) -> None:
        try:
            with self.source.thread_context():
                self._loop()
        except Exception:
            log.exception("recorder thread crashed")
            self.status = Status.UNAVAILABLE
            self._running.clear()

    def _loop(self) -> None:
        src = self.source
        if not src.ensure_running():
            log.error("Live Captions is not available")
            self.status = Status.UNAVAILABLE
            self._running.clear()
            return
        src.hide()
        self._take_baseline()
        self.status = Status.LISTENING

        last, missing, tick, hung = None, 0, 0, 0
        while self.running:
            tick += 1
            if src.is_hung():
                hung += 1
                if hung >= self.HUNG_RESTART_TICKS:
                    log.warning("Live Captions is not responding — restarting it")
                    self._reconnect()
                    hung = 0
                time.sleep(self.POLL_SECONDS)
                continue
            hung = 0
            if tick % 3 == 0:
                src.keep_hidden()

            text = src.read()
            if text is None:
                missing += 1
                if missing >= self.MISSING_RECONNECT_TICKS:
                    log.warning("Live Captions window lost — reconnecting")
                    self._reconnect()
                    missing = 0
            else:
                missing = 0
                if self.status == Status.RECONNECTING:
                    self.status = Status.LISTENING
                if text != last:
                    last = text
                    log.debug("snapshot: %r", text[-200:])
                    with self.lock:
                        self.transcript.update(text)
            self.autosave()
            time.sleep(self.POLL_SECONDS)

    def _reconnect(self) -> None:
        self.status = Status.RECONNECTING
        if self.source.ensure_running():
            self.source.hide()

    def _take_baseline(self) -> None:
        """Whatever is already on screen when we press Start is old — don't record it."""
        # One retry only: right after the window is re-parked the text control may need a moment.
        # Waiting longer would risk swallowing the first words spoken after Start.
        first = self.source.read() or ""
        if not first:
            time.sleep(0.5)
            first = self.source.read() or ""
        with self.lock:
            if first and not self.transcript.lines:
                log.debug("baseline: %r", first[-200:])
                self.transcript.set_baseline(first)

    # ------------------------------------------------------------------ autosave
    def autosave(self, force: bool = False) -> None:
        if not self.autosave_dir:
            return
        now = time.time()
        if not force and now - self._last_autosave < self.AUTOSAVE_SECONDS:
            return
        self._last_autosave = now
        with self.lock:
            n = len(self.transcript.lines)
            if n == 0 or (n == self._saved_count and not force):
                return
            data = self.transcript.export("timestamps", include_partial=False)
            self._saved_count = n
        try:
            os.makedirs(self.autosave_dir, exist_ok=True)
            if not self._session_file:
                name = f"session_{datetime.now():%Y-%m-%d_%H-%M-%S}.txt"
                self._session_file = os.path.join(self.autosave_dir, name)
            tmp = self._session_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data + "\n")
            os.replace(tmp, self._session_file)   # atomic: never leave a half-written file
        except OSError:
            log.exception("autosave failed")
