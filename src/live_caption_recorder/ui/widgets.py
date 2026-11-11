"""Small reusable widgets for the glass UI."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from . import theme


class IconButton(QPushButton):
    def __init__(self, glyph: str, tooltip: str, parent: QWidget | None = None, *,
                 danger: bool = False, size: int = 34, text_font: QFont | None = None):
        super().__init__(glyph, parent)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip.split("  ")[0])
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(size, size)
        if text_font is None:
            text_font = QFont(theme.icon_font_family())
            text_font.setPixelSize(14)
        self.setFont(text_font)
        hover = "rgba(232,17,35,0.9)" if danger else "rgba(255,255,255,0.12)"
        self.setStyleSheet(f"""
            QPushButton {{ color: rgba(255,255,255,0.82); background: transparent; border: none; border-radius: 9px; }}
            QPushButton:hover {{ background: {hover}; color: white; }}
            QPushButton:pressed {{ background: rgba(255,255,255,0.07); }}
            QPushButton:checked {{ color: {theme.ACCENT}; background: rgba(124,210,255,0.14); }}
            QPushButton::menu-indicator {{ image: none; width: 0; }}
        """)


class Toggle(QPushButton):
    """iOS-style switch with a label."""

    def __init__(self, text: str, checked: bool = False, parent: QWidget | None = None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAccessibleName(text)
        self._label = text
        self.setFont(theme.ui_font(12))
        self.setFixedHeight(24)
        self.setMinimumWidth(36 + self.fontMetrics().horizontalAdvance(text) + 8)
        self.setStyleSheet("background: transparent; border: none;")

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        p.setOpacity(1.0 if self.isEnabled() else 0.4)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.ACCENT) if on else QColor(255, 255, 255, 45))
        p.drawRoundedRect(QRectF(0, 5, 28, 15), 7.5, 7.5)
        p.setBrush(QColor("#0d0d12") if on else QColor("white"))
        p.drawEllipse(QRectF(15.5 if on else 2.5, 7.5, 10, 10))
        p.setPen(QColor(255, 255, 255, 200))
        p.drawText(QRect(36, 0, self.width() - 36, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self._label)


class Logo(QWidget):
    def __init__(self, parent: QWidget | None = None, size: int = 26):
        super().__init__(parent)
        self.setFixedSize(size, size)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        theme.paint_logo(p, QRectF(self.rect()))


class Separator(QFrame):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(1, 20)
        self.setStyleSheet("background: rgba(255,255,255,0.14);")


class Toast(QLabel):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("background: rgba(28,28,34,0.95); color: white; border: 1px solid rgba(255,255,255,0.14);"
                           f"border-radius: 15px; padding: 6px 16px; font: 12.5px '{theme.UI_FONT}';")
        self.hide()
        self._timer = QTimer(self, singleShot=True, timeout=self.hide)

    def show_message(self, text: str, ms: int = 2000) -> None:
        self.setText(text)
        self.adjustSize()
        self.show()
        self.raise_()
        self._timer.start(ms)


class ConfirmOverlay(QWidget):
    """In-window confirmation card (keeps the frameless glass look)."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setStyleSheet("background: rgba(0,0,0,0.45); border-radius: 14px;")
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignCenter)
        card = QFrame()
        card.setFixedWidth(360)
        card.setStyleSheet("QFrame { background: rgba(34,34,42,0.98); border: 1px solid rgba(255,255,255,0.14);"
                           " border-radius: 14px; } QLabel { border: none; background: transparent; }")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(6)
        self._title = QLabel()
        self._title.setStyleSheet(f"color: white; font: 600 14px '{theme.UI_FONT}';")
        self._text = QLabel()
        self._text.setWordWrap(True)
        self._text.setStyleSheet(f"color: rgba(255,255,255,0.65); font: 12.5px '{theme.UI_FONT}';")
        lay.addWidget(self._title)
        lay.addWidget(self._text)
        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel = QPushButton("Cancel")
        self._ok = QPushButton()
        for btn, bg, hover in ((self._cancel, "rgba(255,255,255,0.1)", "rgba(255,255,255,0.16)"),
                               (self._ok, "#c42b1c", "#d83b2b")):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"QPushButton {{ background: {bg}; color: white; border: none; border-radius: 8px;"
                              f" padding: 7px 16px; font: 600 12.5px '{theme.UI_FONT}'; }}"
                              f" QPushButton:hover {{ background: {hover}; }}")
            row.addWidget(btn)
        self._cancel.clicked.connect(self.hide)
        self._ok.clicked.connect(self._accept)
        lay.addSpacing(8)
        lay.addLayout(row)
        outer.addWidget(card)
        self._action: Callable[[], None] | None = None
        self.hide()

    def ask(self, title: str, text: str, ok_label: str, action: Callable[[], None]) -> None:
        self._title.setText(title)
        self._text.setText(text)
        self._ok.setText(ok_label)
        self._action = action
        self.setGeometry(self.parentWidget().rect().adjusted(1, 1, -1, -1))
        self.show()
        self.raise_()
        self._ok.setFocus()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key_Escape:
            self.hide()
        elif e.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._accept()
        else:
            super().keyPressEvent(e)

    def _accept(self) -> None:
        self.hide()
        if self._action:
            self._action()
