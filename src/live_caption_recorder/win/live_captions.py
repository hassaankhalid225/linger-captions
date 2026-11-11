"""Control and read the built-in Windows 11 "Live Captions" app.

How it works
------------
* Live Captions renders its text into a XAML ``TextBlock`` (AutomationId
  ``CaptionsTextBlock``); we read it with UI Automation.
* When Live Captions is *minimized* it stops updating that text. When it is moved
  *off-screen* it keeps updating — so we park it far outside the visible desktop and
  remove it from the taskbar. ``restore()`` puts it back when we exit.
* All window calls are asynchronous so a frozen Live Captions can never freeze us; a
  frozen instance is terminated and relaunched.
"""

from __future__ import annotations

import logging
import os
import time

import uiautomation as auto

from . import win32 as w

log = logging.getLogger(__name__)
auto.Logger.SetLogFile(os.devnull)   # uiautomation would otherwise write @AutomationLog.txt into cwd

WINDOW_CLASS = "LiveCaptionsDesktopWindow"
TEXT_AUTOMATION_ID = "CaptionsTextBlock"
OFFSCREEN_MARGIN = 8000


def executable_path() -> str:
    return os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "LiveCaptions.exe")


def is_available() -> bool:
    """Live Captions ships with Windows 11 22H2 and newer."""
    return os.path.exists(executable_path())


class LiveCaptions:
    def __init__(self) -> None:
        self.hwnd: int | None = None
        self._control = None
        self._text = None
        self._orig_pos: tuple[int, int] | None = None
        self._orig_exstyle: int | None = None
        self.hidden = False

    # ------------------------------------------------------------------ lifecycle
    @staticmethod
    def thread_context():
        """UI Automation needs COM initialised on the calling thread."""
        return auto.UIAutomationInitializerInThread()

    @staticmethod
    def _find() -> int | None:
        # Win32 lookup: UI Automation cannot see a window that is currently invisible.
        return w.find_window(WINDOW_CLASS)

    def _launch(self) -> int | None:
        if not is_available():
            log.error("LiveCaptions.exe not found (needs Windows 11 22H2+)")
            return None
        try:
            os.startfile(executable_path())
        except OSError:
            log.exception("could not start Live Captions")
            return None
        for _ in range(60):
            hwnd = self._find()
            if hwnd and w.user32.IsWindowVisible(hwnd):
                break
            time.sleep(0.25)
        time.sleep(2.0)   # let it finish initialising before we restyle the window
        return self._find()

    def is_hung(self) -> bool:
        h = self.hwnd
        return bool(h and w.user32.IsWindow(h) and w.user32.IsHungAppWindow(h))

    def ensure_running(self) -> bool:
        hwnd = self._find()
        if hwnd and w.user32.IsHungAppWindow(hwnd):
            log.warning("terminating unresponsive Live Captions")
            w.terminate_window_process(hwnd)
            for _ in range(20):
                if not self._find():
                    break
                time.sleep(0.25)
            hwnd = None
        if not hwnd:
            hwnd = self._launch()
        if not hwnd:
            return False
        if hwnd != self.hwnd:
            self.hwnd, self.hidden = hwnd, False
        self._ensure_visible()
        self._control = auto.ControlFromHandle(hwnd)
        self._text = None
        return self._control is not None

    # ------------------------------------------------------------------ window parking
    def _ensure_visible(self) -> None:
        h = self.hwnd
        if h and w.user32.IsWindow(h) and (not w.user32.IsWindowVisible(h) or w.user32.IsIconic(h)):
            w.user32.ShowWindowAsync(h, w.SW_SHOWNOACTIVATE)

    def hide(self) -> None:
        """Park the window off-screen and drop its taskbar button. It keeps rendering."""
        h = self.hwnd
        if not h or not w.user32.IsWindow(h) or w.user32.IsHungAppWindow(h):
            return
        if not self.hidden:
            left, top, *_ = w.window_rect(h)
            if left > -OFFSCREEN_MARGIN // 2:
                self._orig_pos = (left, top)
            self._orig_exstyle = w.user32.GetWindowLongPtrW(h, w.GWL_EXSTYLE)
            w.user32.ShowWindowAsync(h, w.SW_HIDE)
            time.sleep(0.15)
            ex = (self._orig_exstyle | w.WS_EX_TOOLWINDOW) & ~w.WS_EX_APPWINDOW
            w.user32.SetWindowLongPtrW(h, w.GWL_EXSTYLE, ex)
            self.hidden = True
        vx, vy = w.virtual_screen_origin()
        flags = w.SWP_NOSIZE | w.SWP_NOZORDER | w.SWP_NOACTIVATE | w.SWP_FRAMECHANGED | w.SWP_ASYNCWINDOWPOS
        w.user32.SetWindowPos(h, None, vx - OFFSCREEN_MARGIN, vy - OFFSCREEN_MARGIN, 0, 0, flags)
        w.user32.ShowWindowAsync(h, w.SW_SHOWNOACTIVATE)

    def keep_hidden(self) -> None:
        """Re-park the window if the user (or Windows) minimized, hid or moved it."""
        h = self.hwnd
        if not h or not w.user32.IsWindow(h) or w.user32.IsHungAppWindow(h):
            return
        left, *_ = w.window_rect(h)
        if w.user32.IsIconic(h) or not w.user32.IsWindowVisible(h) or left > -OFFSCREEN_MARGIN // 2:
            self.hide()

    def restore(self) -> None:
        h = self.hwnd
        if not h or not w.user32.IsWindow(h) or not self.hidden:
            return
        w.user32.ShowWindowAsync(h, w.SW_HIDE)
        time.sleep(0.15)
        if self._orig_exstyle is not None:
            w.user32.SetWindowLongPtrW(h, w.GWL_EXSTYLE, self._orig_exstyle)
        x, y = self._orig_pos or (100, 100)
        flags = w.SWP_NOSIZE | w.SWP_NOZORDER | w.SWP_NOACTIVATE | w.SWP_FRAMECHANGED | w.SWP_ASYNCWINDOWPOS
        w.user32.SetWindowPos(h, None, x, y, 0, 0, flags)
        w.user32.ShowWindowAsync(h, w.SW_SHOWNOACTIVATE)
        self.hidden = False

    # ------------------------------------------------------------------ reading
    def read(self) -> str | None:
        """Current caption text, ``""`` if none yet, ``None`` if the window is gone."""
        try:
            if self._text is None or not self._text.Exists(0, 0):
                if self._control is None or not self.hwnd or not w.user32.IsWindow(self.hwnd):
                    return None
                self._ensure_visible()
                self._text = self._control.TextControl(AutomationId=TEXT_AUTOMATION_ID)
                if not self._text.Exists(0.5, 0.1):
                    self._text = None
                    return ""
            return self._text.Name or ""
        except Exception:
            log.debug("UI Automation read failed", exc_info=True)
            self._text = None
            return None
