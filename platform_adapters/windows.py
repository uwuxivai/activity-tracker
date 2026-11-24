import ctypes
from ctypes import wintypes
from typing import Optional

import psutil

from .base import BasePlatformAdapter, WindowInfo


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


class WindowsPlatformAdapter(BasePlatformAdapter):
    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32

        self._user32.GetForegroundWindow.restype = wintypes.HWND
        self._user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self._user32.GetWindowTextLengthW.restype = ctypes.c_int
        self._user32.GetWindowTextW.argtypes = [
            wintypes.HWND,
            wintypes.LPWSTR,
            ctypes.c_int,
        ]
        self._user32.GetWindowTextW.restype = ctypes.c_int
        self._user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self._user32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LASTINPUTINFO)]
        self._user32.GetLastInputInfo.restype = wintypes.BOOL
        self._kernel32.GetTickCount.restype = wintypes.DWORD

    @property
    def adapter_name(self) -> str:
        return "Windows (WinAPI)"

    def get_active_window(self) -> Optional[WindowInfo]:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return None

        length = self._user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        if length > 0:
            self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value.strip()

        pid_dword = wintypes.DWORD(0)
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_dword))
        pid = int(pid_dword.value)

        app_name = "unknown"
        exe_path = ""
        if pid > 0:
            try:
                proc = psutil.Process(pid)
                app_name = proc.name()
                exe_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                app_name = f"pid:{pid}"

        return WindowInfo(
            app_name=app_name,
            window_title=title,
            executable_path=exe_path,
            pid=pid,
        )

    def get_idle_seconds(self) -> float:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        if not self._user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0

        elapsed_ms = (self._kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
        return elapsed_ms / 1000.0