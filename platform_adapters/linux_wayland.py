import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import psutil
from PySide6.QtCore import ClassInfo, QObject, Slot
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusReply

from .base import BasePlatformAdapter, WindowInfo

_DBUS_SERVICE = "ru.coursework.ActivityTracker"
_DBUS_PATH = "/Tracker"
_DBUS_IFACE = "ru.coursework.ActivityTracker"
_KWIN_PLUGIN_NAME = "activity_tracker_kwin_bridge"

_KWIN_SCRIPT_TEMPLATE = f"""
function report(w) {{
    if (!w) {{
        return;
    }}
    var cls = w.resourceClass ? String(w.resourceClass) : "";
    var caption = w.caption ? String(w.caption) : "";
    var pid = w.pid ? Number(w.pid) : 0;
    callDBus("{_DBUS_SERVICE}", "{_DBUS_PATH}", "{_DBUS_IFACE}", "onWindowChanged", cls, caption, pid);
}}

if (workspace.windowActivated) {{
    workspace.windowActivated.connect(report);
    report(workspace.activeWindow);
}} else if (workspace.clientActivated) {{
    workspace.clientActivated.connect(report);
    report(workspace.activeClient);
}}
"""


@ClassInfo({"D-Bus Interface": _DBUS_IFACE})
class _KWinDBusReceiver(QObject):
    """Принимает события смены активного окна от KWin-скрипта по D-Bus."""

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.latest_window: Optional[WindowInfo] = None

    @Slot(str, str, int)
    def onWindowChanged(self, resource_class: str, caption: str, pid: int) -> None:
        app_name = resource_class or "unknown"
        exe_path = ""
        if pid > 0:
            try:
                proc = psutil.Process(pid)
                app_name = proc.name()
                exe_path = proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass

        self.latest_window = WindowInfo(
            app_name=app_name,
            window_title=caption,
            executable_path=exe_path,
            pid=pid,
        )


class LinuxWaylandAdapter(BasePlatformAdapter):
    def __init__(self) -> None:
        self._compositor = self._detect_compositor()
        self._bus = QDBusConnection.sessionBus()

        self._kwin_receiver: Optional[_KWinDBusReceiver] = None
        self._kwin_script_path: Optional[Path] = None

        if self._compositor == "kwin":
            self._setup_kwin_bridge()

        self._screensaver_iface = QDBusInterface(
            "org.freedesktop.ScreenSaver",
            "/ScreenSaver",
            "org.freedesktop.ScreenSaver",
            self._bus,
        )
        self._mutter_idle_iface = QDBusInterface(
            "org.gnome.Mutter.IdleMonitor",
            "/org/gnome/Mutter/IdleMonitor/Core",
            "org.gnome.Mutter.IdleMonitor",
            self._bus,
        )

    @staticmethod
    def _detect_compositor() -> str:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        if "kde" in desktop or "plasma" in desktop:
            return "kwin"
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
            return "hyprland"
        if os.environ.get("SWAYSOCK"):
            return "sway"
        return "unknown"

    def _setup_kwin_bridge(self) -> None:
        if not self._bus.isConnected():
            return

        self._kwin_receiver = _KWinDBusReceiver()
        self._bus.registerService(_DBUS_SERVICE)
        self._bus.registerObject(
            _DBUS_PATH,
            self._kwin_receiver,
            QDBusConnection.RegisterOption.ExportAllSlots,
        )

        scripting = QDBusInterface(
            "org.kde.KWin",
            "/Scripting",
            "org.kde.kwin.Scripting",
            self._bus,
        )
        if not scripting.isValid():
            return

        scripting.call("unloadScript", _KWIN_PLUGIN_NAME)

        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", prefix="kwin_tracker_", delete=False, encoding="utf-8"
        )
        tmp.write(_KWIN_SCRIPT_TEMPLATE)
        tmp.close()
        self._kwin_script_path = Path(tmp.name)

        reply = QDBusReply(
            scripting.call("loadScript", str(self._kwin_script_path), _KWIN_PLUGIN_NAME)
        )
        if reply.isValid():
            script_id = reply.value()
            script_obj = QDBusInterface(
                "org.kde.KWin",
                f"/Scripting/Script{script_id}",
                "org.kde.kwin.Script",
                self._bus,
            )
            if script_obj.isValid():
                script_obj.call("run")
            else:
                scripting.call("start")

    @property
    def adapter_name(self) -> str:
        return f"Linux (Wayland / {self._compositor})"

    def get_active_window(self) -> Optional[WindowInfo]:
        if self._compositor == "kwin" and self._kwin_receiver is not None:
            return self._kwin_receiver.latest_window
        if self._compositor == "hyprland":
            return self._get_hyprland_window()
        if self._compositor == "sway":
            return self._get_sway_window()
        return None

    def _get_hyprland_window(self) -> Optional[WindowInfo]:
        try:
            out = subprocess.check_output(
                ["hyprctl", "activewindow", "-j"], text=True, timeout=0.5
            )
            data = json.loads(out)
            pid = int(data.get("pid") or 0)
            app_name, exe_path = self._process_from_pid(pid, data.get("class", "unknown"))
            return WindowInfo(
                app_name=app_name,
                window_title=str(data.get("title") or ""),
                executable_path=exe_path,
                pid=pid,
            )
        except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
            return None

    def _get_sway_window(self) -> Optional[WindowInfo]:
        try:
            out = subprocess.check_output(
                ["swaymsg", "-t", "get_tree"], text=True, timeout=0.5
            )
            node = self._find_focused_sway_node(json.loads(out))
            if not node:
                return None
            pid = int(node.get("pid") or 0)
            fallback_name = str(
                node.get("app_id")
                or (node.get("window_properties") or {}).get("class")
                or "unknown"
            )
            app_name, exe_path = self._process_from_pid(pid, fallback_name)
            return WindowInfo(
                app_name=app_name,
                window_title=str(node.get("name") or ""),
                executable_path=exe_path,
                pid=pid,
            )
        except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
            return None

    @classmethod
    def _find_focused_sway_node(cls, node: dict) -> Optional[dict]:
        if node.get("focused") and (node.get("pid") or node.get("app_id")):
            return node
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            found = cls._find_focused_sway_node(child)
            if found:
                return found
        return None

    @staticmethod
    def _process_from_pid(pid: int, fallback: str) -> tuple[str, str]:
        if pid > 0:
            try:
                proc = psutil.Process(pid)
                return proc.name(), proc.exe()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return fallback, ""

    def get_idle_seconds(self) -> float:
        if self._screensaver_iface.isValid():
            reply = QDBusReply(self._screensaver_iface.call("GetSessionIdleTime"))
            if reply.isValid():
                return float(reply.value()) / 1000.0

        if self._mutter_idle_iface.isValid():
            reply = QDBusReply(self._mutter_idle_iface.call("GetIdletime"))
            if reply.isValid():
                return float(reply.value()) / 1000.0

        return 0.0

    def close(self) -> None:
        if self._compositor == "kwin" and self._bus.isConnected():
            scripting = QDBusInterface(
                "org.kde.KWin",
                "/Scripting",
                "org.kde.kwin.Scripting",
                self._bus,
            )
            if scripting.isValid():
                scripting.call("unloadScript", _KWIN_PLUGIN_NAME)
            self._bus.unregisterObject(_DBUS_PATH)
            self._bus.unregisterService(_DBUS_SERVICE)

        if self._kwin_script_path and self._kwin_script_path.exists():
            self._kwin_script_path.unlink(missing_ok=True)