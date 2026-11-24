import time
import os

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot

from platform_adapters import BasePlatformAdapter, create_platform_adapter

from .categorizer import ActivityCategorizer
from .database import ActivityDatabase

from platform_adapters.base import WindowInfo


@dataclass(slots=True)
class TrackerConfig:
    """Настройки цикла опроса и определения состояния AFK."""

    poll_interval_ms: int = 1000
    afk_threshold_sec: float = 180.0
    pulse_timeout_sec: float = 5.0


class _TrackerWorker(QObject):
    """Рабочий объект, живущий в выделенном QThread (с собственным Qt Event Loop)."""

    adapterReady = Signal(str)
    snapshotUpdated = Signal(str, str, float, bool, str)
    dataRecorded = Signal()
    errorOccurred = Signal(str)
    finished = Signal()

    def __init__(
        self,
        db: ActivityDatabase,
        categorizer: ActivityCategorizer,
        config: TrackerConfig,
        adapter_factory: Callable[[], BasePlatformAdapter] = create_platform_adapter,
    ) -> None:
        super().__init__()
        self._db = db
        self._categorizer = categorizer
        self._config = config
        self._adapter_factory = adapter_factory

        self._adapter: Optional[BasePlatformAdapter] = None
        self._timer: Optional[QTimer] = None
        self._paused = False
        self._category_names: dict[int, str] = {}

    def _refresh_category_names(self) -> None:
        self._category_names = {c.id: c.name for c in self._db.get_categories() if c.id is not None}

    @Slot()
    def start_tracking(self) -> None:
        try:
            self._adapter = self._adapter_factory()
            self._refresh_category_names()
            self.adapterReady.emit(self._adapter.adapter_name)

            self._timer = QTimer(self)
            self._timer.setInterval(max(250, self._config.poll_interval_ms))
            self._timer.timeout.connect(self._on_tick)
            self._timer.start()
            self._on_tick()
        except Exception as exc:  # noqa: BLE001
            self.errorOccurred.emit(f"Ошибка запуска трекера: {exc}")

    @Slot()
    def stop_tracking(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None

        if self._adapter is not None:
            try:
                self._adapter.close()
            finally:
                self._adapter = None

        self.finished.emit()

    @Slot(bool)
    def set_paused(self, paused: bool) -> None:
        self._paused = paused

    @Slot(int, float, float)
    def apply_config(
        self, poll_interval_ms: int, afk_threshold_sec: float, pulse_timeout_sec: float
    ) -> None:
        self._config.poll_interval_ms = max(250, poll_interval_ms)
        self._config.afk_threshold_sec = max(10.0, afk_threshold_sec)
        self._config.pulse_timeout_sec = max(2.0, pulse_timeout_sec)
        if self._timer is not None:
            self._timer.setInterval(self._config.poll_interval_ms)

    @Slot()
    def reload_rules_cache(self) -> None:
        self._categorizer.reload_rules(self._db.get_rules())
        self._refresh_category_names()

    def _on_tick(self) -> None:
        if self._paused or self._adapter is None:
            return

        try:
            now = time.time()
            idle_sec = self._adapter.get_idle_seconds()
            is_afk = idle_sec >= self._config.afk_threshold_sec

            app_name = "AFK"
            window_title = "Пользователь неактивен"
            cat_id: Optional[int] = None
            cat_name = "AFK"

            if not is_afk:
                info = self._adapter.get_active_window()
                if info is None:
                    return
                app_name = info.app_name
                window_title = info.window_title
                cat_id = self._categorizer.classify(app_name, window_title)
                cat_name = self._category_names.get(cat_id, "Без категории") if cat_id else "Без категории"

            self._db.record_heartbeat(
                app_name=app_name,
                window_title=window_title,
                timestamp=now,
                step_seconds=self._config.poll_interval_ms / 1000.0,
                is_afk=is_afk,
                category_id=cat_id,
                pulse_timeout=self._config.pulse_timeout_sec,
            )

            self.snapshotUpdated.emit(app_name, window_title, round(idle_sec, 1), is_afk, cat_name)
            self.dataRecorded.emit()
        except Exception as exc:  # noqa: BLE001
            self.errorOccurred.emit(f"Ошибка тика опроса: {exc}")


class TrackerService(QObject):
    """Фасад управления фоновым потоком трекинга для GUI и ViewModel."""

    _SELF_PID = os.getpid()
    _IGNORED_EXECUTABLES = {"python.exe", "pythonw.exe", "python", "python3"}

    adapterReady = Signal(str)
    snapshotUpdated = Signal(str, str, float, bool, str)
    dataRecorded = Signal()
    errorOccurred = Signal(str)

    _cmdSetPaused = Signal(bool)
    _cmdApplyConfig = Signal(int, float, float)
    _cmdReloadRules = Signal()
    _cmdStop = Signal()

    def __init__(
        self,
        db: ActivityDatabase,
        categorizer: Optional[ActivityCategorizer] = None,
        config: Optional[TrackerConfig] = None,
        adapter_factory: Callable[[], BasePlatformAdapter] = create_platform_adapter,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._categorizer = categorizer or ActivityCategorizer(db.get_rules())
        self._config = config or TrackerConfig()

        self._thread = QThread(self)
        self._worker = _TrackerWorker(
            db=self._db,
            categorizer=self._categorizer,
            config=self._config,
            adapter_factory=adapter_factory,
        )
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.start_tracking)
        self._cmdStop.connect(self._worker.stop_tracking)
        self._worker.finished.connect(self._thread.quit)

        self._cmdSetPaused.connect(self._worker.set_paused)
        self._cmdApplyConfig.connect(self._worker.apply_config)
        self._cmdReloadRules.connect(self._worker.reload_rules_cache)

        self._worker.adapterReady.connect(self.adapterReady)
        self._worker.snapshotUpdated.connect(self.snapshotUpdated)
        self._worker.dataRecorded.connect(self.dataRecorded)
        self._worker.errorOccurred.connect(self.errorOccurred)

    def start(self) -> None:
        if not self._thread.isRunning():
            self._thread.start()

    def stop(self) -> None:
        if self._thread.isRunning():
            self._cmdStop.emit()
            self._thread.wait(3000)

    def set_paused(self, paused: bool) -> None:
        self._cmdSetPaused.emit(paused)

    def update_config(
        self, poll_interval_ms: int, afk_threshold_sec: float, pulse_timeout_sec: float = 5.0
    ) -> None:
        self._cmdApplyConfig.emit(poll_interval_ms, afk_threshold_sec, pulse_timeout_sec)

    def reload_rules(self) -> None:
        self._cmdReloadRules.emit()

    def _is_ignored_window(self, info: WindowInfo) -> bool:
        if info.pid and info.pid == self._SELF_PID:
            return True
        app = (info.app_name or "").strip().lower()
        title = (info.window_title or "").strip().lower()
        if app in self._IGNORED_EXECUTABLES and "activity tracker" in title:
            return True
        return False