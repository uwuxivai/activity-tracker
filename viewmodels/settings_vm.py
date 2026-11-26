from typing import Optional

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from core import ActivityDatabase, TrackerService

from .dashboard_vm import resolve_period_bounds


class SettingsVM(QObject):
    """ViewModel настроек трекинга, темы оформления, паузы и экспорта отчётов."""

    settingsChanged = Signal()
    exportStatusChanged = Signal()
    pauseChanged = Signal(bool)
    quittingChanged = Signal()
    databaseReset = Signal()

    def __init__(
        self,
        db: ActivityDatabase,
        tracker: TrackerService,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._tracker = tracker

        self._poll_interval_ms = int(self._db.get_setting("poll_interval_ms", "1000"))
        self._afk_threshold_min = float(self._db.get_setting("afk_threshold_min", "3.0"))
        self._dark_theme = self._db.get_setting("dark_theme", "1") == "1"
        self._is_paused = False
        self._export_status = ""
        self._quitting = False

    def mark_quitting(self) -> None:
        self._quitting = True
        self.quittingChanged.emit()

    @Slot(int, float)
    def saveTrackingSettings(self, poll_ms: int, afk_min: float) -> None:
        self._poll_interval_ms = max(500, min(10000, int(poll_ms)))
        self._afk_threshold_min = max(0.5, min(60.0, round(float(afk_min), 1)))

        self._db.set_setting("poll_interval_ms", str(self._poll_interval_ms))
        self._db.set_setting("afk_threshold_min", str(self._afk_threshold_min))

        pulse = max(5.0, (self._poll_interval_ms / 1000.0) * 3.0)
        self._tracker.update_config(
            self._poll_interval_ms,
            self._afk_threshold_min * 60.0,
            pulse,
        )
        self.settingsChanged.emit()
        self._export_status = "Параметры трекинга сохранены и применены."
        self.exportStatusChanged.emit()

    @Slot(bool)
    def setDarkTheme(self, enabled: bool) -> None:
        if self._dark_theme != enabled:
            self._dark_theme = enabled
            self._db.set_setting("dark_theme", "1" if enabled else "0")
            self.settingsChanged.emit()

    @Slot()
    def togglePause(self) -> None:
        self._is_paused = not self._is_paused
        self._tracker.set_paused(self._is_paused)
        self.settingsChanged.emit()
        self.pauseChanged.emit(self._is_paused)

    @Slot(str, str, str)
    def exportReport(self, file_url: str, fmt: str, period_key: str) -> None:
        local_path = QUrl(file_url).toLocalFile() if file_url.startswith("file:") else file_url
        if not local_path:
            return

        start_ts, end_ts = resolve_period_bounds(period_key)
        try:
            if fmt.lower() == "csv":
                count = self._db.export_csv(local_path, start_ts, end_ts)
            else:
                count = self._db.export_json(local_path, start_ts, end_ts)
            self._export_status = f"Экспортировано записей ({fmt.upper()}): {count} -> {local_path}"
        except OSError as exc:
            self._export_status = f"Ошибка экспорта: {exc}"
        self.exportStatusChanged.emit()

    @Slot()
    def resetDatabase(self) -> None:
        self._db.reset_database()
        self.databaseReset.emit()

    @Property(int, notify=settingsChanged)
    def pollIntervalMs(self) -> int:
        return self._poll_interval_ms

    @Property(float, notify=settingsChanged)
    def afkThresholdMin(self) -> float:
        return self._afk_threshold_min

    @Property(bool, notify=settingsChanged)
    def darkTheme(self) -> bool:
        return self._dark_theme

    @Property(bool, notify=settingsChanged)
    def isPaused(self) -> bool:
        return self._is_paused

    @Property(str, notify=exportStatusChanged)
    def exportStatus(self) -> str:
        return self._export_status

    @Property(bool, notify=quittingChanged)
    def quitting(self) -> bool:
        return self._quitting