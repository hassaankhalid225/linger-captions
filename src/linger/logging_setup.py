"""Rotating file log in %LOCALAPPDATA%\\Linger\\logs + crash hooks."""

from __future__ import annotations

import logging
import os
import sys
import threading
from logging.handlers import RotatingFileHandler

from .config import log_dir

LOG_FILE_NAME = "app.log"


def log_file_path() -> str:
    return os.path.join(log_dir(), LOG_FILE_NAME)


def setup_logging(debug: bool = False) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    handler = RotatingFileHandler(log_file_path(), maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(fmt)
    root.addHandler(handler)
    logging.getLogger("comtypes").setLevel(logging.WARNING)   # very chatty at INFO
    if sys.stderr is not None:   # pythonw has no console
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        root.addHandler(console)


def install_exception_hooks(on_crash=None) -> None:
    """Log every uncaught exception; optionally show it to the user."""
    log = logging.getLogger("crash")

    def handle(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log.critical("uncaught exception", exc_info=(exc_type, exc, tb))
        if on_crash:
            try:
                on_crash(exc)
            except Exception:
                pass

    sys.excepthook = handle
    threading.excepthook = lambda args: handle(args.exc_type, args.exc_value, args.exc_traceback)
