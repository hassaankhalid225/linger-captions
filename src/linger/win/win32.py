"""Thin, typed ctypes bindings for the few Win32 calls we need."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

if sys.platform != "win32":  # pragma: no cover
    raise ImportError("linger.win.win32 requires Windows")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x2, 0x4, 0x10
SWP_FRAMECHANGED, SWP_ASYNCWINDOWPOS = 0x20, 0x4000
SW_HIDE, SW_SHOWNOACTIVATE, SW_RESTORE = 0, 4, 9
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
WDA_NONE, WDA_EXCLUDEFROMCAPTURE = 0x0, 0x11
PROCESS_TERMINATE = 0x0001
DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND = 33, 2
ERROR_ALREADY_EXISTS = 183

_HWND = wintypes.HWND
user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
user32.FindWindowW.restype = _HWND
user32.GetWindowLongPtrW.argtypes = [_HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [_HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowPos.argtypes = [_HWND, _HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.GetWindowRect.argtypes = [_HWND, ctypes.POINTER(wintypes.RECT)]
for _fn in ("IsIconic", "IsWindow", "IsWindowVisible", "IsHungAppWindow", "SetForegroundWindow"):
    getattr(user32, _fn).argtypes = [_HWND]
user32.ShowWindowAsync.argtypes = [_HWND, ctypes.c_int]
user32.GetWindowThreadProcessId.argtypes = [_HWND, ctypes.POINTER(wintypes.DWORD)]
user32.SetWindowDisplayAffinity.argtypes = [_HWND, wintypes.DWORD]
user32.GetWindowDisplayAffinity.argtypes = [_HWND, ctypes.POINTER(wintypes.DWORD)]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
dwmapi.DwmSetWindowAttribute.argtypes = [_HWND, wintypes.DWORD, wintypes.LPCVOID, wintypes.DWORD]


def find_window(class_name: str | None = None, title: str | None = None) -> int | None:
    return user32.FindWindowW(class_name, title) or None


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def terminate_window_process(hwnd: int) -> None:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return
    handle = kernel32.OpenProcess(PROCESS_TERMINATE, False, pid.value)
    if handle:
        kernel32.TerminateProcess(handle, 1)
        kernel32.CloseHandle(handle)


def virtual_screen_origin() -> tuple[int, int]:
    return user32.GetSystemMetrics(SM_XVIRTUALSCREEN), user32.GetSystemMetrics(SM_YVIRTUALSCREEN)


# ---------------------------------------------------------------- our own window
def set_capture_excluded(hwnd: int, excluded: bool) -> bool:
    """Hide (or show) a window from screen capture, screen sharing and recordings.

    Requires Windows 10 2004 or newer. Returns False if the OS refused."""
    return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE if excluded else WDA_NONE))


def is_capture_excluded(hwnd: int) -> bool:
    value = wintypes.DWORD(0)
    user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(value))
    return value.value == WDA_EXCLUDEFROMCAPTURE


def set_rounded_corners(hwnd: int) -> None:
    pref = ctypes.c_int(DWMWCP_ROUND)
    dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(pref), ctypes.sizeof(pref))


class SingleInstance:
    """Named mutex so only one copy of the app runs per user session."""

    def __init__(self, name: str):
        self._handle = kernel32.CreateMutexW(None, False, f"Local\\{name}.SingleInstance")
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    def release(self) -> None:
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None


def focus_existing_window(title: str) -> bool:
    hwnd = find_window(None, title)
    if not hwnd:
        return False
    user32.ShowWindowAsync(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    return True
