from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class WindowInfo:
    app_name: str
    window_title: str
    executable_path: str = ""
    pid: int = 0


class BasePlatformAdapter(ABC):
    """Единый интерфейс сбора пользовательской активности для разных ОС."""

    @property
    @abstractmethod
    def adapter_name(self) -> str:
        """Человекочитаемое имя активного бэкенда (для логов и UI)."""

    @abstractmethod
    def get_active_window(self) -> Optional[WindowInfo]:
        """Возвращает данные о текущем активном окне или None."""

    @abstractmethod
    def get_idle_seconds(self) -> float:
        """Возвращает время бездействия пользователя в секундах."""

    def close(self) -> None:
        """Освобождение системных ресурсов при завершении приложения."""