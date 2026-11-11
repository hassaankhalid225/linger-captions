"""System tray icon: quick access to show/hide, start/stop and copy."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .. import APP_NAME
from . import theme
from .main_window import MainWindow


class TrayIcon(QSystemTrayIcon):
    def __init__(self, window: MainWindow):
        super().__init__(theme.app_icon(), window)
        self.window = window
        self.setToolTip(APP_NAME)
        menu = QMenu()
        self.act_show = menu.addAction("Hide window", self.toggle_window)
        self.act_rec = menu.addAction("Start recording", window.toggle_recording)
        menu.addAction("Copy transcript", window.copy_all)
        menu.addSeparator()
        menu.addAction("Quit", window.request_quit)
        menu.aboutToShow.connect(self._sync)
        self._menu = menu   # keep a reference
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        QTimer(self, timeout=self._sync_tooltip, interval=1000).start()

    def _sync(self) -> None:
        visible = self.window.isVisible() and not self.window.isMinimized()
        self.act_show.setText("Hide window" if visible else "Show window")
        self.act_rec.setText("Stop recording" if self.window.rec.running else "Start recording")

    def _sync_tooltip(self) -> None:
        state = "recording" if self.window.rec.running else "idle"
        self.setToolTip(f"{APP_NAME} — {state}")

    def toggle_window(self) -> None:
        w = self.window
        if w.isVisible() and not w.isMinimized():
            w.hide()
        else:
            w.showNormal()
            w.raise_()
            w.activateWindow()

    def _on_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.toggle_window()
