from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import Property, QObject, QTimer, Signal, Slot

from core import ActivityDatabase

from .apps_model import AppsListModel


def format_duration(seconds: float) -> str:
    sec = int(round(max(0.0, seconds)))
    hours, rem = divmod(sec, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours} ч {minutes:02d} мин"
    if minutes > 0:
        return f"{minutes} мин {secs:02d} с"
    return f"{secs} с"


def resolve_period_bounds(period_key: str) -> tuple[float, float]:
    """Вычисляет границы [start_ts, end_ts] для выбранного пресета периода."""
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if period_key == "yesterday":
        start = today_start - timedelta(days=1)
        end = today_start
    elif period_key == "week":
        start = today_start - timedelta(days=6)
        end = now
    elif period_key == "month":
        start = today_start - timedelta(days=29)
        end = now
    else:  # "today"
        start = today_start
        end = now

    return start.timestamp(), max(start.timestamp() + 1.0, end.timestamp())


class DashboardVM(QObject):
    """ViewModel главного дашборда, графиков, таймлайна дня и живого статуса."""

    statsChanged = Signal()
    liveChanged = Signal()
    timelineChanged = Signal()
    adapterChanged = Signal()

    def __init__(
        self,
        db: ActivityDatabase,
        apps_model: AppsListModel,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._apps_model = apps_model

        self._period_key = "today"
        self._timeline_day_offset = 0  # 0 = сегодня, -1 = вчера и т.д.

        # Живой статус из TrackerService
        self._adapter_name = "Инициализация..."
        self._live_app = "—"
        self._live_title = "Ожидание первого тика..."
        self._live_category = "—"
        self._live_idle = 0.0
        self._live_is_afk = False

        # Агрегированные метрики дашборда
        self._active_time_text = "0 с"
        self._afk_time_text = "0 с"
        self._productive_time_text = "0 с"
        self._distracting_time_text = "0 с"
        self._productivity_index = 0.0
        self._category_chart_data: list[dict] = []
        self._hourly_chart_data: list[dict] = []

        # Данные таймлайна
        self._timeline_date_label = ""
        self._timeline_segments: list[dict] = []
        self._timeline_sessions: list[dict] = []

        # Периодическое обновление аналитики (раз в 5 секунд для снижения нагрузки на CPU/SQLite)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._refresh_timer.start()

        self.refresh()

    # ------------------------------------------------------------------
    # Слоты, вызываемые из TrackerService и QML
    # ------------------------------------------------------------------

    @Slot(str)
    def onAdapterReady(self, name: str) -> None:
        self._adapter_name = name
        self.adapterChanged.emit()

    @Slot(str, str, float, bool, str)
    def onSnapshotUpdated(
        self,
        app_name: str,
        window_title: str,
        idle_sec: float,
        is_afk: bool,
        category_name: str,
    ) -> None:
        self._live_app = app_name
        self._live_title = window_title or app_name
        self._live_idle = idle_sec
        self._live_is_afk = is_afk
        self._live_category = category_name
        self.liveChanged.emit()

    @Slot(str)
    def setPeriod(self, period_key: str) -> None:
        if period_key != self._period_key:
            self._period_key = period_key
            self.refresh()

    @Slot(int)
    def shiftTimelineDay(self, delta: int) -> None:
        new_offset = min(0, self._timeline_day_offset + delta)
        if new_offset != self._timeline_day_offset:
            self._timeline_day_offset = new_offset
            self._refresh_timeline()

    @Slot()
    def resetTimelineToday(self) -> None:
        self._timeline_day_offset = 0
        self._refresh_timeline()

    @Slot()
    def refresh(self) -> None:
        start_ts, end_ts = resolve_period_bounds(self._period_key)
        stats = self._db.get_period_stats(start_ts, end_ts, top_limit=12)

        self._active_time_text = format_duration(stats.active_seconds)
        self._afk_time_text = format_duration(stats.afk_seconds)
        self._productive_time_text = format_duration(stats.productive_seconds)
        self._distracting_time_text = format_duration(stats.distracting_seconds)
        self._productivity_index = stats.productivity_index

        self._apps_model.set_items(stats.top_apps)

        self._category_chart_data = [
            {
                "name": c.name,
                "color": c.color,
                "seconds": c.total_seconds,
                "durationText": format_duration(c.total_seconds),
                "share": c.share_percent,
            }
            for c in stats.categories
        ]

        max_hour_sec = max((h.active_seconds for h in stats.hourly), default=1.0) or 1.0
        self._hourly_chart_data = [
            {
                "hour": h.hour,
                "label": f"{h.hour:02d}",
                "activeSeconds": round(h.active_seconds, 1),
                "productiveSeconds": round(h.productive_seconds, 1),
                "activeRatio": min(1.0, h.active_seconds / max_hour_sec),
                "productiveRatio": min(1.0, h.productive_seconds / max_hour_sec),
                "durationText": format_duration(h.active_seconds),
            }
            for h in stats.hourly
        ]

        self.statsChanged.emit()
        self._refresh_timeline()

    def _refresh_timeline(self) -> None:
        base_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
            days=self._timeline_day_offset
        )
        day_start_ts = base_day.timestamp()
        day_end_ts = (base_day + timedelta(days=1)).timestamp()
        total_day_sec = 86400.0

        self._timeline_date_label = base_day.strftime("%d.%m.%Y")
        if self._timeline_day_offset == 0:
            self._timeline_date_label += " (Сегодня)"
        elif self._timeline_day_offset == -1:
            self._timeline_date_label += " (Вчера)"

        events = self._db.get_events_in_range(day_start_ts, day_end_ts)
        segments: list[dict] = []
        for ev in events:
            start_frac = max(0.0, (ev.start_ts - day_start_ts) / total_day_sec)
            width_frac = max(0.0015, (ev.end_ts - ev.start_ts) / total_day_sec)
            t1 = datetime.fromtimestamp(ev.start_ts).strftime("%H:%M:%S")
            t2 = datetime.fromtimestamp(ev.end_ts).strftime("%H:%M:%S")
            segments.append(
                {
                    "startFraction": start_frac,
                    "widthFraction": min(1.0 - start_frac, width_frac),
                    "appName": ev.app_name,
                    "windowTitle": ev.window_title or ev.app_name,
                    "categoryName": ev.category_name,
                    "color": ev.category_color,
                    "timeRange": f"{t1} – {t2}",
                    "durationText": format_duration(ev.duration),
                    "isAfk": ev.is_afk,
                }
            )

        self._timeline_segments = segments
        # Журнал сессий в обратном хронологическом порядке (последние события сверху)
        self._timeline_sessions = list(reversed(segments))
        self.timelineChanged.emit()

    # ------------------------------------------------------------------
    # QML Properties
    # ------------------------------------------------------------------

    @Property(str, notify=adapterChanged)
    def adapterName(self) -> str:
        return self._adapter_name

    @Property(str, notify=liveChanged)
    def liveApp(self) -> str:
        return self._live_app

    @Property(str, notify=liveChanged)
    def liveTitle(self) -> str:
        return self._live_title

    @Property(str, notify=liveChanged)
    def liveCategory(self) -> str:
        return self._live_category

    @Property(float, notify=liveChanged)
    def liveIdle(self) -> float:
        return self._live_idle

    @Property(bool, notify=liveChanged)
    def liveIsAfk(self) -> bool:
        return self._live_is_afk

    @Property(str, notify=statsChanged)
    def periodKey(self) -> str:
        return self._period_key

    @Property(str, notify=statsChanged)
    def activeTimeText(self) -> str:
        return self._active_time_text

    @Property(str, notify=statsChanged)
    def afkTimeText(self) -> str:
        return self._afk_time_text

    @Property(str, notify=statsChanged)
    def productiveTimeText(self) -> str:
        return self._productive_time_text

    @Property(str, notify=statsChanged)
    def distractingTimeText(self) -> str:
        return self._distracting_time_text

    @Property(float, notify=statsChanged)
    def productivityIndex(self) -> float:
        return self._productivity_index

    @Property("QVariantList", notify=statsChanged)
    def categoryChartData(self) -> list[dict]:
        return self._category_chart_data

    @Property("QVariantList", notify=statsChanged)
    def hourlyChartData(self) -> list[dict]:
        return self._hourly_chart_data

    @Property(str, notify=timelineChanged)
    def timelineDateLabel(self) -> str:
        return self._timeline_date_label

    @Property("QVariantList", notify=timelineChanged)
    def timelineSegments(self) -> list[dict]:
        return self._timeline_segments

    @Property("QVariantList", notify=timelineChanged)
    def timelineSessions(self) -> list[dict]:
        return self._timeline_sessions