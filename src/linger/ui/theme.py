"""Colours, fonts, icon glyphs and the app icon."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPen, QPixmap

ACCENT = "#7cd2ff"
ACCENT_2 = "#a99bff"
TEXT = "#f5f5f7"
REC = "#ff4d5e"
WARN = "#ffbe46"
RADIUS = 16

UI_FONT = "Segoe UI"
DISPLAY_FONTS = ["Segoe UI Variable Display", "Segoe UI"]

# Segoe Fluent Icons / Segoe MDL2 Assets code points
class Glyph:
    COPY = ""
    SAVE = ""
    DELETE = ""
    PIN = ""
    CHEVRON_DOWN = ""
    CHEVRON_UP = ""
    MINIMIZE = ""
    CLOSE = ""
    MORE = ""
    SHIELD = ""


@lru_cache(maxsize=1)
def icon_font_family() -> str:
    families = set(QFontDatabase.families())
    for name in ("Segoe Fluent Icons", "Segoe MDL2 Assets"):
        if name in families:
            return name
    return "Segoe UI Symbol"


def ui_font(px: int, weight: QFont.Weight = QFont.Normal) -> QFont:
    f = QFont(UI_FONT)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def display_font(px: int, weight: QFont.Weight = QFont.Medium) -> QFont:
    f = QFont(DISPLAY_FONTS[0])
    f.setFamilies(DISPLAY_FONTS)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


LOGO_TOP, LOGO_MID, LOGO_BOTTOM = "#46c6ff", "#6f8bff", "#9b6bff"


def paint_logo(p: QPainter, rect: QRectF) -> None:
    """The Linger mark: an "L" whose foot trails off into fading dots — words that stay.

    Drawn on a 100x100 grid and scaled to ``rect``; docs/logo.svg is the same drawing.
    """
    p.save()
    p.translate(rect.topLeft())
    s = min(rect.width(), rect.height()) / 100.0
    p.scale(s, s)
    p.setRenderHint(QPainter.Antialiasing)

    bg = QLinearGradient(0, 0, 100, 100)
    bg.setColorAt(0, QColor(LOGO_TOP))
    bg.setColorAt(0.5, QColor(LOGO_MID))
    bg.setColorAt(1, QColor(LOGO_BOTTOM))
    p.setPen(Qt.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(0, 0, 100, 100), 26, 26)

    sheen = QLinearGradient(0, 0, 0, 55)
    sheen.setColorAt(0, QColor(255, 255, 255, 70))
    sheen.setColorAt(1, QColor(255, 255, 255, 0))
    p.setBrush(sheen)
    p.drawRoundedRect(QRectF(0, 0, 100, 100), 26, 26)

    pen = QPen(QColor("white"), 12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawPolyline([QPointF(26, 25), QPointF(26, 73), QPointF(50, 73)])
    p.setPen(Qt.NoPen)
    for x, alpha in ((65, 200), (79, 115)):
        p.setBrush(QColor(255, 255, 255, alpha))
        p.drawEllipse(QPointF(x, 73), 6, 6)
    p.restore()


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        paint_logo(p, QRectF(0, 0, size, size))
        p.end()
        icon.addPixmap(pm)
    return icon


APP_STYLESHEET = f"""
QToolTip {{ background: #24242b; color: #eee; border: 1px solid rgba(255,255,255,0.15);
            padding: 5px 8px; border-radius: 6px; font: 12px '{UI_FONT}'; }}
QMenu {{ background: #23232a; color: #eee; border: 1px solid rgba(255,255,255,0.12);
         border-radius: 10px; padding: 6px; font: 13px '{UI_FONT}'; }}
QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: rgba(255,255,255,0.09); }}
QMenu::item:disabled {{ color: rgba(255,255,255,0.35); }}
QMenu::separator {{ height: 1px; background: rgba(255,255,255,0.1); margin: 5px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; margin-left: 6px; }}
QMenu::indicator:checked {{ image: none; background: {ACCENT}; border-radius: 4px; }}
QMenu::indicator:unchecked {{ image: none; border: 1px solid rgba(255,255,255,0.3); border-radius: 4px; }}
"""
