import os
import sys

from .base import BasePlatformAdapter


def create_platform_adapter() -> BasePlatformAdapter:
    """Определяет ОС и дисплейный сервер, возвращая подходящий адаптер."""
    if sys.platform == "win32":
        from .windows import WindowsPlatformAdapter

        return WindowsPlatformAdapter()

    if sys.platform.startswith("linux"):
        session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
        is_wayland = session_type == "wayland" or bool(os.environ.get("WAYLAND_DISPLAY"))

        if is_wayland:
            from .linux_wayland import LinuxWaylandAdapter

            return LinuxWaylandAdapter()

        from .linux_x11 import LinuxX11Adapter

        return LinuxX11Adapter()

    raise NotImplementedError(f"Платформа '{sys.platform}' не поддерживается.")