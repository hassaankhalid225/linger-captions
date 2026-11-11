"""User settings (persisted with QSettings in the registry) and standard paths."""

from __future__ import annotations

import os
from dataclasses import dataclass, fields

from PySide6.QtCore import QSettings

from . import APP_ID, APP_NAME


def documents_dir() -> str:
    try:
        from PySide6.QtCore import QStandardPaths
        path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        if path:
            return path
    except Exception:  # pragma: no cover
        pass
    return os.path.join(os.path.expanduser("~"), "Documents")


def default_transcripts_dir() -> str:
    return os.path.join(documents_dir(), APP_NAME)


def data_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_ID)
    os.makedirs(path, exist_ok=True)
    return path


def log_dir() -> str:
    path = os.path.join(data_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    return path


@dataclass
class Settings:
    font_px: int = 24
    always_on_top: bool = True
    private_mode: bool = False          # hide window from screen capture / sharing
    glass_blur: bool = True             # only possible in private mode
    timestamps: bool = False
    autosave: bool = True
    start_on_launch: bool = False
    transcripts_dir: str = ""
    window_geometry: str = ""           # "x,y,w" of the compact bar

    @property
    def effective_transcripts_dir(self) -> str:
        return self.transcripts_dir or default_transcripts_dir()

    # ------------------------------------------------------------------ persistence
    @classmethod
    def load(cls) -> Settings:
        qs = QSettings(APP_ID, "app")
        s = cls()
        for f in fields(cls):
            raw = qs.value(f.name)
            if raw is None:
                continue
            default = getattr(s, f.name)
            try:
                if isinstance(default, bool):
                    value = raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes")
                elif isinstance(default, int):
                    value = int(raw)
                else:
                    value = str(raw)
            except (TypeError, ValueError):
                continue
            setattr(s, f.name, value)
        s.font_px = max(12, min(56, s.font_px))
        return s

    def save(self) -> None:
        qs = QSettings(APP_ID, "app")
        names = {f.name for f in fields(self)}
        for key in qs.allKeys():          # drop settings from older versions
            if key not in names:
                qs.remove(key)
        for name in names:
            qs.setValue(name, getattr(self, name))
        qs.sync()
