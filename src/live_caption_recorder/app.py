"""Application entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from . import APP_ID, APP_NAME, __version__

log = logging.getLogger(__name__)


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="live-caption-recorder", description=APP_NAME)
    p.add_argument("--start", action="store_true", help="start recording immediately")
    p.add_argument("--debug", action="store_true", help="verbose logging")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("--screenshot", metavar="PNG", help=argparse.SUPPRESS)          # dev: save a window grab
    p.add_argument("--screenshot-delay", type=int, default=4000, help=argparse.SUPPRESS)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if sys.platform != "win32":
        print(f"{APP_NAME} only runs on Windows 11 (it reads the built-in Live Captions app).", file=sys.stderr)
        return 2

    from .logging_setup import install_exception_hooks, log_file_path, setup_logging
    setup_logging(args.debug)
    log.info("%s %s starting (python %s)", APP_NAME, __version__, sys.version.split()[0])

    from .win import win32
    instance = win32.SingleInstance(APP_ID)
    if instance.already_running:
        log.info("another instance is running — focusing it")
        win32.focus_existing_window(APP_NAME)
        return 0

    # Qt must create the application (and set DPI awareness) before uiautomation is imported.
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(APP_ID)
    app.setQuitOnLastWindowClosed(False)   # the tray can keep us alive while the window is hidden

    from .ui import theme
    app.setStyleSheet(theme.APP_STYLESHEET)
    app.setWindowIcon(theme.app_icon())

    def on_crash(exc: BaseException) -> None:
        QMessageBox.critical(None, APP_NAME, f"Something went wrong:\n\n{exc}\n\nDetails were written to\n{log_file_path()}")

    install_exception_hooks(on_crash)

    from .config import Settings
    from .core.recorder import Recorder
    from .ui.main_window import MainWindow
    from .ui.tray import TrayIcon
    from .win.live_captions import LiveCaptions, is_available

    settings = Settings.load()
    recorder = Recorder(LiveCaptions(), settings.effective_transcripts_dir if settings.autosave else None)
    window = MainWindow(recorder, settings)
    tray = TrayIcon(window) if QSystemTrayIcon.isSystemTrayAvailable() else None
    app.setQuitOnLastWindowClosed(tray is None)

    def shutdown() -> None:
        log.info("shutting down")
        window.close()
        recorder.shutdown()
        if tray:
            tray.hide()
        instance.release()
        app.quit()

    window.quit_requested.connect(shutdown)
    window.show()
    if tray:
        tray.show()

    if not is_available():
        window.toast_msg("Live Captions was not found — Windows 11 22H2 or newer is required")
    elif args.start or settings.start_on_launch:
        QTimer.singleShot(400, window.toggle_recording)

    if args.screenshot:
        path = os.path.abspath(args.screenshot)
        QTimer.singleShot(args.screenshot_delay, lambda: window.grab().save(path))

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
