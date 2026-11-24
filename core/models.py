from dataclasses import dataclass, field
from typing import Optional


@dataclass(slots=True)
class Category:
    """Категория активности (например: Разработка, Учёба, Развлечения)."""

    id: Optional[int]
    name: str
    color: str = "#64748b"
    # 1 = продуктивно, 0 = нейтрально, -1 = отвлекает
    productivity: int = 0


@dataclass(slots=True)
class Rule:
    """Правило автоматической классификации окна в категорию."""

    id: Optional[int]
    pattern: str
    match_field: str  # "app_name" или "window_title"
    is_regex: bool = False
    # Меньшее значение означает более высокий приоритет (проверяется раньше)
    priority: int = 100
    category_id: int = 0


@dataclass(slots=True)
class ActivityEvent:
    """Непрерывный интервал пользовательской активности (или простоя AFK)."""

    id: Optional[int]
    app_name: str
    window_title: str
    start_ts: float
    end_ts: float
    is_afk: bool = False
    category_id: Optional[int] = None
    category_name: str = "Без категории"
    category_color: str = "#64748b"
    productivity: int = 0

    @property
    def duration(self) -> float:
        return max(0.0, self.end_ts - self.start_ts)


@dataclass(slots=True)
class AppStat:
    """Агрегированная статистика по конкретному приложению."""

    app_name: str
    total_seconds: float
    share_percent: float
    category_name: str
    category_color: str


@dataclass(slots=True)
class CategoryStat:
    """Агрегированная статистика по категории."""

    category_id: Optional[int]
    name: str
    color: str
    productivity: int
    total_seconds: float
    share_percent: float


@dataclass(slots=True)
class HourlyStat:
    """Почасовое распределение активности (0..23) для столбчатого графика."""

    hour: int
    active_seconds: float = 0.0
    afk_seconds: float = 0.0
    productive_seconds: float = 0.0


@dataclass(slots=True)
class PeriodStats:
    """Полная аналитическая сводка за выбранный временной интервал."""

    start_ts: float
    end_ts: float
    active_seconds: float = 0.0
    afk_seconds: float = 0.0
    productive_seconds: float = 0.0
    neutral_seconds: float = 0.0
    distracting_seconds: float = 0.0
    productivity_index: float = 0.0
    top_apps: list[AppStat] = field(default_factory=list)
    categories: list[CategoryStat] = field(default_factory=list)
    hourly: list[HourlyStat] = field(default_factory=list)