"""The frameless frosted-glass caption window."""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QGuiApplication,
    QKeySequence,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
    QShortcut,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..config import Settings, log_dir
from ..core.recorder import Recorder, Status
from ..win import win32
from . import theme
from .theme import Glyph
from .widgets import ConfirmOverlay, IconButton, Logo, Separator, Toast, Toggle

log = logging.getLogger(__name__)

COMPACT_H, EXPANDED_H = 220, 600
MIN_W = 600
BACKDROP_MS = 120

EXPORT_FILTERS = {
    "Text (*.txt)": ("text", ".txt"),
    "Text with timestamps (*.txt)": ("timestamps", ".txt"),
    "Markdown (*.md)": ("markdown", ".md"),
    "Subtitles (*.srt)": ("srt", ".srt"),
}


class MainWindow(QWidget):
    quit_requested = Signal()

    def __init__(self, recorder: Recorder, settings: Settings):
        super().__init__()
        self.rec = recorder
        self.settings = settings
        self.expanded = False
        self.follow = True
        self._backdrop = None
        self._shown_count = 0
        self._shown_version = 0
        self._partial_pos: int | None = None
        self._partial_text = ""
        self._caret_on = True
        self._pulse = False
        self._capture_ok = True

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(theme.app_icon())
        flags = Qt.FramelessWindowHint | Qt.Window
        if settings.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        self.setMinimumSize(MIN_W, 170)

        self._build_ui()
        self._build_menu()
        self._restore_geometry()
        self._apply_font()

        QTimer(self, timeout=self._refresh, interval=250).start()
        QTimer(self, timeout=self._blink, interval=530).start()
        QTimer(self, timeout=self._update_backdrop, interval=BACKDROP_MS).start()
        QTimer(self, timeout=self._guard_capture_mode, interval=1500).start()

        for seq, fn in (("Ctrl+Shift+C", self.copy_all), ("Ctrl+S", self.save_as), ("Ctrl+=", lambda: self.font_step(2)),
                        ("Ctrl+-", lambda: self.font_step(-2)), ("Ctrl+R", self.toggle_recording),
                        ("Ctrl+E", self.toggle_expand), ("Ctrl+Q", self.request_quit)):
            QShortcut(QKeySequence(seq), self, activated=fn)

    # ================================================================== layout
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(7, 4, 7, 7)
        root.setSpacing(0)

        # ---- header
        self.header = QWidget(self)
        self.header.setFixedHeight(50)
        self.header.setMouseTracking(True)
        h = QHBoxLayout(self.header)
        h.setContentsMargins(10, 0, 2, 0)
        h.setSpacing(8)
        h.addWidget(Logo())
        title = QLabel("Live Captions")
        title.setFont(theme.display_font(14, QFont.DemiBold))
        title.setStyleSheet("color: rgba(255,255,255,0.95); background: transparent;")
        h.addWidget(title)
        h.addSpacing(4)
        self.pill = QLabel()
        self.pill.setTextFormat(Qt.RichText)
        self.pill.setFont(theme.ui_font(12, QFont.DemiBold))
        self.pill.setFixedHeight(26)
        h.addWidget(self.pill)
        h.addStretch(1)

        self.main_btn = QPushButton()
        self.main_btn.setCursor(Qt.PointingHandCursor)
        self.main_btn.setFocusPolicy(Qt.NoFocus)
        self.main_btn.setFixedHeight(32)
        self.main_btn.setFont(theme.ui_font(13, QFont.DemiBold))
        self.main_btn.setToolTip("Start / stop recording   Ctrl+R")
        self.main_btn.clicked.connect(self.toggle_recording)
        h.addWidget(self.main_btn)
        h.addSpacing(4)

        for glyph, tip, slot in ((Glyph.COPY, "Copy all   Ctrl+Shift+C", self.copy_all),
                                 (Glyph.SAVE, "Save / export   Ctrl+S", self.save_as),
                                 (Glyph.DELETE, "Clear transcript", self.ask_clear)):
            b = IconButton(glyph, tip)
            b.clicked.connect(slot)
            h.addWidget(b)
        h.addWidget(Separator())
        b = IconButton("A−", "Smaller text   Ctrl+−", text_font=theme.ui_font(12, QFont.DemiBold))
        b.clicked.connect(lambda: self.font_step(-2))
        h.addWidget(b)
        b = IconButton("A+", "Bigger text   Ctrl+=", text_font=theme.ui_font(15, QFont.DemiBold))
        b.clicked.connect(lambda: self.font_step(2))
        h.addWidget(b)
        self.private_btn = IconButton(Glyph.SHIELD, "")
        self.private_btn.setCheckable(True)
        self.private_btn.clicked.connect(lambda: self.set_private_mode(self.private_btn.isChecked()))
        h.addWidget(self.private_btn)
        self.expand_btn = IconButton(Glyph.CHEVRON_DOWN, "Expand transcript   Ctrl+E")
        self.expand_btn.setCheckable(True)
        self.expand_btn.clicked.connect(self.toggle_expand)
        h.addWidget(self.expand_btn)
        self.more_btn = IconButton(Glyph.MORE, "Settings")
        h.addWidget(self.more_btn)
        h.addWidget(Separator())
        b = IconButton(Glyph.MINIMIZE, "Minimize — recording continues")
        b.clicked.connect(self.showMinimized)
        h.addWidget(b)
        b = IconButton(Glyph.CLOSE, "Quit   Ctrl+Q", danger=True)
        b.clicked.connect(self.request_quit)
        h.addWidget(b)
        root.addWidget(self.header)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background: rgba(255,255,255,0.08);")
        root.addWidget(line)

        # ---- captions
        self.text = QTextBrowser(self)
        self.text.setFrameShape(QFrame.NoFrame)
        self.text.setOpenLinks(False)
        self.text.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        self.text.viewport().setAutoFillBackground(False)
        self.text.setCursorWidth(0)   # read-only view: no blinking text caret
        self.text.setStyleSheet(f"""
            QTextBrowser {{ background: transparent; border: none; color: {theme.TEXT};
                            padding: 10px 16px 6px 16px; selection-background-color: rgba(124,210,255,0.35); }}
            QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px 4px 0; }}
            QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.18); border-radius: 4px; min-height: 30px; }}
            QScrollBar::handle:vertical:hover {{ background: rgba(255,255,255,0.3); }}
            QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page
                {{ background: none; height: 0; }}
        """)
        self.text.verticalScrollBar().valueChanged.connect(self._on_scroll)
        root.addWidget(self.text, 1)

        self.empty = QLabel(self.text)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        self.empty.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.empty.setStyleSheet("background: transparent;")

        self.jump = QPushButton("↓  Latest", self)
        self.jump.setCursor(Qt.PointingHandCursor)
        self.jump.setFocusPolicy(Qt.NoFocus)
        self.jump.setStyleSheet(f"QPushButton {{ background: rgba(30,30,38,0.92); color: {theme.ACCENT};"
                                " border: 1px solid rgba(255,255,255,0.14); border-radius: 14px; padding: 5px 14px;"
                                f" font: 600 12px '{theme.UI_FONT}'; }} QPushButton:hover {{ background: rgba(45,45,56,0.95); }}")
        self.jump.hide()
        self.jump.clicked.connect(lambda: self._scroll_to_bottom(force=True))

        # ---- footer (expanded mode)
        self.footer = QWidget(self)
        self.footer.setFixedHeight(40)
        fl = QHBoxLayout(self.footer)
        fl.setContentsMargins(16, 0, 12, 0)
        fl.setSpacing(16)
        self.stats = QLabel()
        self.stats.setTextFormat(Qt.RichText)
        self.stats.setStyleSheet(f"color: rgba(255,255,255,0.6); font: 12px '{theme.UI_FONT}'; background: transparent;")
        fl.addWidget(self.stats)
        fl.addStretch(1)
        self.stamp_toggle = Toggle("Timestamps", self.settings.timestamps)
        self.stamp_toggle.toggled.connect(self.set_timestamps)
        fl.addWidget(self.stamp_toggle)
        folder = QPushButton("Transcripts folder  ↗")
        folder.setCursor(Qt.PointingHandCursor)
        folder.setFocusPolicy(Qt.NoFocus)
        folder.setStyleSheet(f"QPushButton {{ color: {theme.ACCENT}; background: transparent; border: none;"
                             f" font: 12px '{theme.UI_FONT}'; }} QPushButton:hover {{ text-decoration: underline; }}")
        folder.clicked.connect(self.open_transcripts_folder)
        fl.addWidget(folder)
        self.footer.hide()
        root.addWidget(self.footer)

        self.toast = Toast(self)
        self.confirm = ConfirmOverlay(self)

    def _build_menu(self) -> None:
        m = QMenu(self)
        m.setAttribute(Qt.WA_TranslucentBackground)
        m.setWindowFlags(m.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)

        def check(text, value, slot):
            a = QAction(text, m, checkable=True, checked=value)
            a.toggled.connect(slot)
            m.addAction(a)
            return a

        self.act_top = check("Always on top", self.settings.always_on_top, self.set_always_on_top)
        self.act_private = check("Private mode — hide from screen sharing", self.settings.private_mode,
                                 self.set_private_mode)
        self.act_blur = check("Glass blur (private mode only)", self.settings.glass_blur, self.set_glass_blur)
        self.act_stamps = check("Show timestamps", self.settings.timestamps, self.set_timestamps)
        m.addSeparator()
        self.act_autosave = check("Auto-save transcripts", self.settings.autosave, self.set_autosave)
        check("Start recording when the app opens", self.settings.start_on_launch,
              lambda v: self._set_setting("start_on_launch", v))
        m.addAction("Open transcripts folder", self.open_transcripts_folder)
        m.addAction("Change transcripts folder…", self.change_transcripts_folder)
        m.addSeparator()
        m.addAction("Open log folder", lambda: os.startfile(log_dir()))
        m.addAction(f"About {APP_NAME}", self.show_about)
        self.more_btn.setMenu(m)
        self._sync_private_ui()

    # ================================================================== glass painting
    def showEvent(self, e) -> None:
        super().showEvent(e)
        try:
            win32.set_rounded_corners(int(self.winId()))
        except OSError:
            pass
        self._apply_capture_mode()
        QTimer.singleShot(300, self._guard_capture_mode)

    def _blur_active(self) -> bool:
        # Blur samples the screen *behind* us, which only works while we are excluded from capture.
        return self.settings.glass_blur and self.settings.private_mode and self._capture_ok

    def _apply_capture_mode(self) -> None:
        self._capture_ok = win32.set_capture_excluded(int(self.winId()), self.settings.private_mode)
        if self.settings.private_mode and not self._capture_ok:
            log.warning("SetWindowDisplayAffinity failed — Windows 10 2004+ is required for private mode")
        self._sync_private_ui()

    def _guard_capture_mode(self) -> None:
        """Windows can reset the affinity when the native window is recreated — keep it in sync."""
        if self.isVisible() and win32.is_capture_excluded(int(self.winId())) != self.settings.private_mode:
            self._apply_capture_mode()

    def _sync_private_ui(self) -> None:
        on = self.settings.private_mode
        self.private_btn.setChecked(on)
        self.private_btn.setToolTip("Private mode ON — hidden from screen sharing & recordings" if on
                                    else "Private mode OFF — click to hide this window from screen sharing")
        if hasattr(self, "act_blur"):
            self.act_blur.setEnabled(on)

    def _update_backdrop(self) -> None:
        if not self._blur_active() or not self.isVisible() or self.isMinimized():
            return
        if not win32.is_capture_excluded(int(self.winId())):   # never sample ourselves
            self._apply_capture_mode()
            return
        screen = self.screen()
        if screen is None:
            return
        g, sg = self.geometry(), screen.geometry()
        pm = screen.grabWindow(0, g.x() - sg.x(), g.y() - sg.y(), g.width(), g.height())
        if pm.isNull():
            return
        w, h = max(1, g.width()), max(1, g.height())
        img = pm.toImage()
        # cheap but smooth blur: aggressive downscale, then two smooth upscales
        for div in (8, 32, 6):
            img = img.scaled(max(1, w // div), max(1, h // div), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self._backdrop = img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), theme.RADIUS, theme.RADIUS)
        p.setClipPath(path)
        if self._blur_active() and self._backdrop is not None:
            p.drawImage(self.rect(), self._backdrop)
            p.fillRect(self.rect(), QColor(14, 14, 20, 140))
        else:
            p.fillRect(self.rect(), QColor(14, 14, 20, 178))
        for cx, color, radius in ((0, QColor(124, 210, 255, 34), 0.45), (self.width(), QColor(169, 155, 255, 28), 0.4)):
            glow = QRadialGradient(cx, 0, self.width() * radius)
            glow.setColorAt(0, color)
            glow.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            p.fillRect(self.rect(), glow)
        sheen = QLinearGradient(0, 0, 0, 70)
        sheen.setColorAt(0, QColor(255, 255, 255, 22))
        sheen.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(0, 0, self.width(), 70), sheen)
        p.setClipping(False)
        border = QLinearGradient(0, 0, 0, self.height())
        border.setColorAt(0, QColor(255, 255, 255, 70))
        border.setColorAt(0.5, QColor(255, 255, 255, 26))
        border.setColorAt(1, QColor(255, 255, 255, 40))
        p.setPen(QPen(border, 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

    # ================================================================== frameless move / resize
    EDGE = 7
    _CURSORS = {
        Qt.LeftEdge: Qt.SizeHorCursor, Qt.RightEdge: Qt.SizeHorCursor,
        Qt.TopEdge: Qt.SizeVerCursor, Qt.BottomEdge: Qt.SizeVerCursor,
        Qt.LeftEdge | Qt.TopEdge: Qt.SizeFDiagCursor, Qt.RightEdge | Qt.BottomEdge: Qt.SizeFDiagCursor,
        Qt.RightEdge | Qt.TopEdge: Qt.SizeBDiagCursor, Qt.LeftEdge | Qt.BottomEdge: Qt.SizeBDiagCursor,
    }

    def _edges_at(self, pos):
        x, y, e = pos.x(), pos.y(), self.EDGE
        edges = Qt.Edge(0)
        if x <= e:
            edges |= Qt.LeftEdge
        if x >= self.width() - e:
            edges |= Qt.RightEdge
        if y <= e:
            edges |= Qt.TopEdge
        if y >= self.height() - e:
            edges |= Qt.BottomEdge
        return edges

    def mouseMoveEvent(self, e) -> None:
        self.setCursor(self._CURSORS.get(self._edges_at(e.position().toPoint()), Qt.ArrowCursor))

    def mousePressEvent(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return
        edges = self._edges_at(e.position().toPoint())
        if edges:
            self.windowHandle().startSystemResize(edges)
        elif e.position().y() < self.header.geometry().bottom() + 4:
            self.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, e) -> None:
        if e.position().y() < self.header.geometry().bottom():
            self.toggle_expand()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        if self.confirm.isVisible():
            self.confirm.setGeometry(self.rect().adjusted(1, 1, -1, -1))
        self._place_floating()
        QTimer.singleShot(0, self._update_backdrop)

    def moveEvent(self, e) -> None:
        super().moveEvent(e)
        self._update_backdrop()

    def _place_floating(self) -> None:
        self.empty.setGeometry(self.text.rect())
        self.jump.adjustSize()
        bottom = self.height() - (self.footer.height() + 10 if self.footer.isVisible() else 12)
        self.jump.move(self.width() - self.jump.width() - 24, bottom - self.jump.height())
        self.toast.adjustSize()
        self.toast.move((self.width() - self.toast.width()) // 2, bottom - self.toast.height())

    def _restore_geometry(self) -> None:
        avail = QGuiApplication.primaryScreen().availableGeometry()
        w = min(1240, int(avail.width() * 0.7))
        rect = QRect(avail.x() + (avail.width() - w) // 2, avail.y() + 12, w, COMPACT_H)
        try:
            x, y, sw = (int(v) for v in self.settings.window_geometry.split(","))
            saved = QRect(x, y, max(MIN_W, sw), COMPACT_H)
            if any(s.availableGeometry().intersects(saved) for s in QGuiApplication.screens()):
                rect = saved
        except ValueError:
            pass
        self.setGeometry(rect)

    def _remember_geometry(self) -> None:
        g = self.geometry()
        self._set_setting("window_geometry", f"{g.x()},{g.y()},{g.width()}")

    # ================================================================== transcript rendering
    def _fmt(self, kind: str) -> QTextCharFormat:
        f = QTextCharFormat()
        fs = self.settings.font_px
        if kind == "ts":
            f.setFont(theme.display_font(max(10, int(fs * 0.5)), QFont.DemiBold))
            f.setForeground(QColor(255, 255, 255, 105))
        else:
            f.setFont(theme.display_font(fs, QFont.Medium))
            f.setForeground(QColor(theme.TEXT if kind == "text" else theme.ACCENT))
        return f

    def _append(self, cursor: QTextCursor, lines) -> None:
        ts_fmt, text_fmt = self._fmt("ts"), self._fmt("text")
        for ln in lines:
            if self.settings.timestamps:
                if not cursor.atStart():
                    cursor.insertBlock()
                cursor.insertText(time.strftime("%H:%M:%S", time.localtime(ln.time)) + "   ", ts_fmt)
                cursor.insertText(ln.text, text_fmt)
            else:
                cursor.insertText(ln.text + " ", text_fmt)

    def _set_partial(self, partial: str, force: bool = False) -> None:
        if partial == self._partial_text and not force:
            return
        self._partial_text = partial
        doc = self.text.document()
        cur = QTextCursor(doc)
        if self._partial_pos is not None:
            cur.setPosition(min(self._partial_pos, doc.characterCount() - 1))
            cur.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            cur.removeSelectedText()
        cur.movePosition(QTextCursor.End)
        self._partial_pos = cur.position()
        if partial:
            if self.settings.timestamps and not cur.atStart():
                cur.insertBlock()
                cur.insertText("· · ·      ", self._fmt("ts"))
            cur.insertText(partial, self._fmt("partial"))
            caret = self._fmt("partial")
            if not self._caret_on:
                caret.setForeground(QColor(0, 0, 0, 0))
            cur.insertText(" ▏", caret)

    def _rebuild(self) -> None:
        with self.rec.lock:
            lines = list(self.rec.transcript.lines)
            partial = self.rec.transcript.partial if self.rec.running else ""
            self._shown_count, self._shown_version = len(lines), self.rec.transcript.version
        self.text.clear()
        self._partial_pos, self._partial_text = None, ""
        self._append(QTextCursor(self.text.document()), lines)
        self._set_partial(partial, force=True)
        if self.follow:
            self._scroll_to_bottom()

    def _refresh(self) -> None:
        tr = self.rec.transcript
        with self.rec.lock:
            rebuild = tr.version != self._shown_version
            new = [] if rebuild else list(tr.lines[self._shown_count:])
            partial = tr.partial if self.rec.running else ""
            count, words = len(tr.lines), tr.word_count
        was_following = self.follow
        if rebuild:
            self._rebuild()
        else:
            if new:
                self._set_partial("", force=True)
                cur = QTextCursor(self.text.document())
                cur.movePosition(QTextCursor.End)
                self._append(cur, new)
                self._partial_pos = None
                self._shown_count = count
                self._set_partial(partial, force=True)
            else:
                self._set_partial(partial)
            if (new or partial) and was_following:
                self._scroll_to_bottom()
            elif new:
                self.jump.show()
                self._place_floating()
        self.stats.setText(f"<b style='color:white'>{words}</b>&nbsp; words &nbsp;&nbsp; "
                           f"<b style='color:white'>{count}</b>&nbsp; sentences")
        self._update_status()
        self.empty.setVisible(not (count or partial))

    def _blink(self) -> None:
        self._pulse = not self._pulse
        if self.rec.running and self._partial_text:
            self._caret_on = not self._caret_on
            self._set_partial(self._partial_text, force=True)
        if self.rec.running:
            self._update_status()

    def _on_scroll(self, _value: int) -> None:
        sb = self.text.verticalScrollBar()
        self.follow = sb.value() >= sb.maximum() - 8
        if self.follow:
            self.jump.hide()

    def _scroll_to_bottom(self, force: bool = False) -> None:
        if force:
            self.follow = True
        sb = self.text.verticalScrollBar()
        sb.setValue(sb.maximum())
        self.jump.hide()

    # ================================================================== status
    def _update_status(self) -> None:
        r = self.rec
        el = r.elapsed()
        t = (f"{el // 3600}:" if el >= 3600 else "") + f"{el // 60 % 60:02d}:{el % 60:02d}"
        pill = "border-radius: 13px; padding: 0 12px; background: {}; border: 1px solid {}; color: {};"
        warn = pill.format("rgba(255,190,70,0.14)", "rgba(255,190,70,0.4)", "#ffe2a8")
        neutral = pill.format("rgba(255,255,255,0.08)", "rgba(255,255,255,0.14)", "rgba(255,255,255,0.75)")
        if r.status == Status.UNAVAILABLE:
            css, txt = warn, "●&nbsp; Live Captions unavailable"
        elif r.running and r.status in (Status.STARTING, Status.RECONNECTING):
            css, txt = warn, f"●&nbsp; {r.status.value.capitalize()}…"
        elif r.running:
            dot = theme.REC if self._pulse else "rgba(255,77,94,0.35)"
            css = pill.format("rgba(255,77,94,0.16)", "rgba(255,77,94,0.45)", "#ffd7db")
            txt = f"<span style='color:{dot}'>●</span>&nbsp; REC&nbsp; {t}"
        elif el > 0:
            css, txt = neutral, f"❚❚&nbsp; Paused&nbsp; {t}"
        else:
            css, txt = neutral, "●&nbsp; Ready"
        if self.pill.text() != txt:
            self.pill.setStyleSheet(css)
            self.pill.setText(txt)

        label = "■   Stop" if r.running else ("▶   Resume" if el > 0 else "▶   Start")
        if self.main_btn.text() != label:
            self.main_btn.setText(label)
            if r.running:
                self.main_btn.setStyleSheet(
                    "QPushButton { background: rgba(255,77,94,0.18); color: #ff9aa4; border: 1px solid rgba(255,77,94,0.5);"
                    " border-radius: 16px; padding: 0 18px; } QPushButton:hover { background: rgba(255,77,94,0.28); }")
            else:
                self.main_btn.setStyleSheet(
                    f"QPushButton {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {theme.ACCENT},"
                    f" stop:1 {theme.ACCENT_2}); color: #0b0b12; border: none; border-radius: 16px; padding: 0 18px; }}"
                    " QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #9adcff, stop:1 #bdb2ff); }")

        if r.status == Status.UNAVAILABLE:
            head, sub = ("Live Captions could not be started",
                         "Requires Windows 11 22H2 or newer. Press Win + Ctrl + L once to set it up, then press Start.")
        elif r.running:
            head, sub = "Listening…", "Play any video, meeting or audio — captions will keep building up here."
        else:
            head, sub = ("Captions from any audio on your PC",
                         "Press Start — every line stays here until you stop. Minimize freely; recording continues.")
        html = (f"<div style='font: 600 17px \"{theme.UI_FONT}\"; color: white'>{head}</div>"
                f"<div style='font: 13px \"{theme.UI_FONT}\"; color: rgba(255,255,255,0.6); margin-top:6px'>{sub}</div>")
        if self.empty.text() != html:
            self.empty.setText(html)

    # ================================================================== actions
    def toggle_recording(self) -> None:
        if self.rec.running:
            self.rec.stop()
        else:
            self.rec.start()
        self._update_status()

    def _export(self, fmt: str) -> str:
        with self.rec.lock:
            return self.rec.transcript.export(fmt)

    def copy_all(self) -> None:
        data = self._export("timestamps" if self.settings.timestamps else "text")
        if not data.strip():
            self.toast_msg("Nothing to copy yet")
            return
        QApplication.clipboard().setText(data)
        self.toast_msg(f"✓  {len(data.split())} words copied")

    def save_as(self) -> None:
        if not self._export("text").strip():
            self.toast_msg("Nothing to save yet")
            return
        default = os.path.join(self.settings.effective_transcripts_dir, f"captions_{datetime.now():%Y-%m-%d_%H-%M}")
        os.makedirs(self.settings.effective_transcripts_dir, exist_ok=True)
        preferred = "Text with timestamps (*.txt)" if self.settings.timestamps else "Text (*.txt)"
        path, chosen = QFileDialog.getSaveFileName(self, "Save transcript", default + ".txt",
                                                   ";;".join(EXPORT_FILTERS), preferred)
        if not path:
            return
        fmt, ext = EXPORT_FILTERS.get(chosen, ("text", ".txt"))
        if not os.path.splitext(path)[1]:
            path += ext
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._export(fmt) + "\n")
        except OSError as exc:
            log.exception("save failed")
            self.toast_msg(f"Could not save: {exc.strerror}")
            return
        self.toast_msg(f"✓  Saved {os.path.basename(path)}")

    def ask_clear(self) -> None:
        if not self._shown_count and not self._partial_text:
            return
        self.confirm.ask("Clear transcript?",
                         "All captions in this window will be removed. Auto-saved files are kept.",
                         "Clear", self._do_clear)

    def _do_clear(self) -> None:
        self.rec.clear()
        self._rebuild()
        self.toast_msg("Cleared")

    def request_quit(self) -> None:
        if not self._shown_count:
            self.quit_requested.emit()
            return
        note = ("Your transcript has been auto-saved." if self.settings.autosave
                else "Auto-save is off — unsaved captions will be lost.")
        self.confirm.ask(f"Quit {APP_NAME}?", note, "Quit", self.quit_requested.emit)

    def toast_msg(self, text: str) -> None:
        self.toast.show_message(text)
        self._place_floating()

    def font_step(self, delta: int) -> None:
        self._set_setting("font_px", max(12, min(56, self.settings.font_px + delta)))
        self._apply_font()

    def _apply_font(self) -> None:
        self.text.document().setDefaultFont(theme.display_font(self.settings.font_px))
        self._rebuild()

    def toggle_expand(self) -> None:
        self.expanded = not self.expanded
        self.expand_btn.setChecked(self.expanded)
        self.expand_btn.setText(Glyph.CHEVRON_UP if self.expanded else Glyph.CHEVRON_DOWN)
        self.expand_btn.setToolTip(("Compact bar" if self.expanded else "Expand transcript") + "   Ctrl+E")
        self.footer.setVisible(self.expanded)
        g = self.geometry()
        anim = QPropertyAnimation(self, b"geometry", self)
        anim.setDuration(220)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.setStartValue(g)
        anim.setEndValue(QRect(g.x(), g.y(), g.width(), EXPANDED_H if self.expanded else COMPACT_H))
        anim.finished.connect(lambda: self._scroll_to_bottom(force=True))
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    # ---- settings
    def _set_setting(self, name: str, value) -> None:
        setattr(self.settings, name, value)
        self.settings.save()

    def set_always_on_top(self, on: bool) -> None:
        self._set_setting("always_on_top", on)
        geo = self.geometry()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, on)   # recreates the native window
        self.setGeometry(geo)
        self.show()
        self._apply_capture_mode()

    def set_private_mode(self, on: bool) -> None:
        self._set_setting("private_mode", bool(on))
        self.act_private.blockSignals(True)
        self.act_private.setChecked(bool(on))
        self.act_private.blockSignals(False)
        self._apply_capture_mode()
        self._update_backdrop()
        self.update()
        if on and not self._capture_ok:
            self.toast_msg("Private mode needs Windows 10 (2004) or newer")
        else:
            self.toast_msg("Private mode on — hidden from screen sharing" if on else "Private mode off")

    def set_glass_blur(self, on: bool) -> None:
        self._set_setting("glass_blur", on)
        self._update_backdrop()
        self.update()

    def set_timestamps(self, on: bool) -> None:
        self._set_setting("timestamps", on)
        for w in (self.stamp_toggle, self.act_stamps):
            w.blockSignals(True)
            w.setChecked(on)
            w.blockSignals(False)
        self.stamp_toggle.update()
        self._rebuild()

    def set_autosave(self, on: bool) -> None:
        self._set_setting("autosave", on)
        self.rec.autosave_dir = self.settings.effective_transcripts_dir if on else None

    def open_transcripts_folder(self) -> None:
        path = self.settings.effective_transcripts_dir
        os.makedirs(path, exist_ok=True)
        os.startfile(path)

    def change_transcripts_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose transcripts folder", self.settings.effective_transcripts_dir)
        if path:
            self._set_setting("transcripts_dir", path)
            if self.settings.autosave:
                self.rec.autosave_dir = path
            self.toast_msg(f"Transcripts will be saved to {path}")

    def show_about(self) -> None:
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b> {__version__}<br><br>"
            "Keeps every line from Windows Live Captions until you stop, so you can copy, "
            "save or export the full transcript.<br><br>"
            "Captions are produced on-device by Windows; nothing is sent to the internet.")

    # ================================================================== lifecycle
    def closeEvent(self, e) -> None:
        self._remember_geometry()
        super().closeEvent(e)
