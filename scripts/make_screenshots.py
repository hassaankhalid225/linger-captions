"""Render README screenshots (docs/screenshot-*.png) with a scripted demo transcript.

Live Captions is not touched: a fake caption source "speaks" a canned talk, and the window is
composited onto a neutral gradient so no part of your real desktop ends up in the image.

    python scripts/make_screenshots.py
"""

from __future__ import annotations

import contextlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QRadialGradient  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

DEMO = (
    "Welcome back everyone. Today we're looking at how the new release pipeline works. "
    "Every merge to main now runs the full test suite on Windows and Linux. "
    "If everything passes, a signed build is published to the staging channel within ten minutes. "
    "We cut the average release time from two days to about forty minutes. "
    "The next step is rolling this out to the mobile team in March. "
    "Let's take a few questions before we move on to the roadmap."
)

OUT_DIR = os.path.join(ROOT, "docs")
PAD = 56


class DemoSource:
    """Pretends to be Live Captions: the text grows a few words per poll."""

    def __init__(self) -> None:
        self.words = DEMO.split()
        self.n = 0
        self.limit = len(self.words)
        self.reads = 0

    def thread_context(self):
        return contextlib.nullcontext()

    def ensure_running(self) -> bool:
        return True

    def hide(self) -> None: ...
    def keep_hidden(self) -> None: ...
    def restore(self) -> None: ...

    def is_hung(self) -> bool:
        return False

    def read(self) -> str:
        self.reads += 1
        if self.reads <= 2:          # nothing on screen yet when Start is pressed (baseline is empty)
            return ""
        self.n = min(self.limit, self.n + 4)
        return " ".join(self.words[: self.n])


def framed(win) -> QImage:
    """Window grab on a soft gradient backdrop with a drop shadow."""
    shot = win.grab().toImage()
    dpr = shot.devicePixelRatio()
    shot.setDevicePixelRatio(1)
    pad = int(PAD * dpr)
    w, h = shot.width() + 2 * pad, shot.height() + 2 * pad
    out = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    bg = QLinearGradient(0, 0, w, h)
    bg.setColorAt(0, QColor("#1d2b64"))
    bg.setColorAt(0.55, QColor("#3a2a6b"))
    bg.setColorAt(1, QColor("#0f4c5c"))
    p.fillRect(out.rect(), bg)
    for cx, cy, color in ((0.2, 0.15, QColor(90, 200, 255, 90)), (0.85, 0.9, QColor(200, 120, 255, 80))):
        glow = QRadialGradient(QPointF(w * cx, h * cy), max(w, h) * 0.45)
        glow.setColorAt(0, color)
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(out.rect(), glow)
    radius = 14 * dpr
    for i in range(14, 0, -1):   # cheap layered shadow
        path = QPainterPath()
        path.addRoundedRect(QRectF(pad - i, pad - i + 8 * dpr, shot.width() + 2 * i, shot.height() + 2 * i), radius + i, radius + i)
        p.fillPath(path, QColor(0, 0, 0, 9))
    p.drawImage(pad, pad, shot)
    p.end()
    return out


def main() -> int:
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])

    from live_caption_recorder.config import Settings
    from live_caption_recorder.core.recorder import Recorder
    from live_caption_recorder.ui import theme
    from live_caption_recorder.ui.main_window import MainWindow

    Settings.save = lambda self: None   # never touch the user's real settings
    app.setStyleSheet(theme.APP_STYLESHEET)

    settings = Settings(autosave=False, always_on_top=False)
    src = DemoSource()
    src.limit = 34                      # compact shot: about three lines, nothing scrolled off
    rec = Recorder(src, None)
    rec.POLL_SECONDS = 0.12
    win = MainWindow(rec, settings)
    win.resize(1000, win.height())
    win.move(-20000, -20000)            # render off-screen so stray clicks/keys can't reach it
    win.setAttribute(Qt.WA_ShowWithoutActivating)
    win.show()
    os.makedirs(OUT_DIR, exist_ok=True)

    def save(name: str) -> None:
        path = os.path.join(OUT_DIR, name)
        framed(win).save(path)
        print("saved", path)

    def expanded() -> None:
        save("screenshot-compact.png")
        src.limit = len(src.words)
        win.set_timestamps(True)
        win.toggle_expand()
        QTimer.singleShot(4000, lambda: (save("screenshot-expanded.png"), rec.shutdown(), app.quit()))

    QTimer.singleShot(300, win.toggle_recording)
    QTimer.singleShot(4000, expanded)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
