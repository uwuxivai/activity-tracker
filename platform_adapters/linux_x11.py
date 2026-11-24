import ctypes
from ctypes.util import find_library
from typing import Optional

import psutil
from Xlib import X, display
from Xlib.error import BadWindow

from .base import BasePlatformAdapter, WindowInfo


class _XScreenSaverInfo(ctypes.Structure):
    _fields_ = [
        ("window", ctypes.c_ulong),
        ("state", ctypes.c_int),
        ("kind", ctypes.c_int),
        ("til_or_since", ctypes.c_ulong),
        ("idle", ctypes.c_ulong),
        ("event_mask", ctypes.c_ulong),
    ]


class LinuxX11Adapter(BasePlatformAdapter):
    def __init__(self) -> None:
        self._display = display.Display()
        self._root = self._display.screen().root

        self._atom_active = self._display.intern_atom("_NET_ACTIVE_WINDOW")
        self._atom_wm_name = self._display.intern_atom("_NET_WM_NAME")
        self._atom_wm_pid = self._display.intern_atom("_NET_WM_PID")
        self._atom_utf8 = self._display.intern_atom("UTF8_STRING")

        self._libx11 = None
        self._libxss = None
        self._c_display = None
        self._c_root = 0
        self._xss_info = None
        self._init_xss()

    def _init_xss(self) -> None:
        x11_path = find_library("X11")
        xss_path = find_library("Xss")
        if not x11_path or not xss_path:
            return

        libx11 = ctypes.cdll.LoadLibrary(x11_path)
        libxss = ctypes.cdll.LoadLibrary(xss_path)

        libx11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        libx11.XOpenDisplay.restype = ctypes.c_void_p
        libx11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        libx11.XDefaultRootWindow.restype = ctypes.c_ulong
        libx11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        libx11.XFree.argtypes = [ctypes.c_void_p]

        libxss.XScreenSaverAllocInfo.restype = ctypes.POINTER(_XScreenSaverInfo)
        libxss.XScreenSaverQueryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(_XScreenSaverInfo),
        ]
        libxss.XScreenSaverQueryInfo.restype = ctypes.c_int

        c_display = libx11.XOpenDisplay(None)
        if not c_display:
            return

        self._libx11 = libx11
        self._libxss = libxss
        self._c_display = c_display
        self._c_root = libx11.XDefaultRootWindow(c_display)
        self._xss_info = libxss.XScreenSaverAllocInfo()

    @property
    def adapter_name(self) -> str:
        return "Linux (X11 / EWMH + libXss)"

    def get_active_window(self) -> Optional[WindowInfo]:
        try:
            prop = self._root.get_full_property(self._atom_active, X.AnyPropertyType)
            if not prop or not prop.value:
                return None

            win_id = prop.value[0]
            if win_id == 0:
                return None

            win = self._display.create_resource_object("window", win_id)
            title = self._read_title(win)
            pid = self._read_pid(win)
            app_name, exe_path = self._resolve_process(win, pid)

            return WindowInfo(
                app_name=app_name,
                window_title=title,
                executable_path=exe_path,
                pid=pid,
            )
        except BadWindow:
            return None

    def _read_title(self, win) -> str:
        prop = win.get_full_property(self._atom_wm_name, self._atom_utf8)
        if prop and prop.value:
            val = prop.value
            return val.decode("utf-8", errors="replace") if isinstance(val, bytes) else str(val)

        legacy_name = win.get_wm_name()
        if isinstance(legacy_name, bytes):
            return legacy_name.decode("utf-8", errors="replace")
        return str(legacy_name or "")

    def _read_pid(self, win) -> int:
        prop = win.get_full_property(self._atom_wm_pid, X.AnyPropertyType)
        if prop and prop.value:
            return int(prop.value[0])
        return 0

    def _resolve_process(self, win, pid: int) -> tuple[str, str]:
        if pid > 0:
            try:
                proc = psutil.Process(pid)
                return proc.name(), proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        wm_class = win.get_wm_class()
        if wm_class:
            return str(wm_class[-1]), ""
        return "unknown", ""

    def get_idle_seconds(self) -> float:
        if not (self._libxss and self._c_display and self._xss_info):
            return 0.0
        status = self._libxss.XScreenSaverQueryInfo(
            self._c_display, self._c_root, self._xss_info
        )
        if status == 0:
            return 0.0
        return self._xss_info.contents.idle / 1000.0

    def close(self) -> None:
        if self._libx11 and self._xss_info:
            self._libx11.XFree(self._xss_info)
            self._xss_info = None
        if self._libx11 and self._c_display:
            self._libx11.XCloseDisplay(self._c_display)
            self._c_display = None
        self._display.close()