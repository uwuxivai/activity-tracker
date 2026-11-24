import os
import sys
from pathlib import Path

# Фиксируем кроссплатформенный стиль Controls для корректной кастомизации на Windows и Linux
os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from core import ActivityCategorizer, ActivityDatabase, TrackerConfig, TrackerService
from viewmodels import AppsListModel, DashboardVM, RulesVM, SettingsVM


def _create_tray_icon() -> QIcon:
    """Генерирует векторную иконку трея программно"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor("#2563eb"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(4, 4, 56, 56)

    pen = QPen(QColor("#f8fafc"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    painter.setPen(pen)
    painter.drawLine(32, 32, 32, 16)
    painter.drawLine(32, 32, 44, 38)
    painter.end()

    return QIcon(pixmap)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Activity Tracker")
    app.setOrganizationName("Coursework")
    app.setQuitOnLastWindowClosed(False)

    icon = _create_tray_icon()
    app.setWindowIcon(icon)

    data_dir = Path.home() / ".activity_tracker"
    db = ActivityDatabase(data_dir / "activity.db")
    categorizer = ActivityCategorizer(db.get_rules())

    poll_ms = int(db.get_setting("poll_interval_ms", "1000"))
    afk_min = float(db.get_setting("afk_threshold_min", "3.0"))
    tracker = TrackerService(
        db=db,
        categorizer=categorizer,
        config=TrackerConfig(
            poll_interval_ms=poll_ms,
            afk_threshold_sec=afk_min * 60.0,
            pulse_timeout_sec=max(5.0, (poll_ms / 1000.0) * 3.0),
        ),
    )

    apps_model = AppsListModel()
    dashboard_vm = DashboardVM(db=db, apps_model=apps_model)
    rules_vm = RulesVM(db=db, categorizer=categorizer)
    settings_vm = SettingsVM(db=db, tracker=tracker)

    # Связь сигналов между фоновым сервисом и ViewModel
    tracker.adapterReady.connect(dashboard_vm.onAdapterReady)
    tracker.snapshotUpdated.connect(dashboard_vm.onSnapshotUpdated)
    rules_vm.rulesUpdated.connect(tracker.reload_rules)
    rules_vm.rulesUpdated.connect(dashboard_vm.refresh)

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("appsModel", apps_model)
    ctx.setContextProperty("dashboardVM", dashboard_vm)
    ctx.setContextProperty("rulesVM", rules_vm)
    ctx.setContextProperty("settingsVM", settings_vm)

    qml_file = Path(__file__).resolve().parent / "qml" / "Main.qml"
    engine.load(qml_file.as_uri())

    if not engine.rootObjects():
        db.close()
        return -1

    root_window = engine.rootObjects()[0]

    # Системный трей
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Activity Tracker")

    tray_menu = QMenu()
    act_show = QAction("Открыть окно", tray_menu)
    act_pause = QAction("Приостановить трекинг", tray_menu)
    act_quit = QAction("Выход", tray_menu)

    def show_window() -> None:
        root_window.show()
        root_window.raise_()
        root_window.requestActivate()

    def quit_app() -> None:
        settings_vm.mark_quitting()
        tray.hide()
        app.quit()

    def on_pause_changed(paused: bool) -> None:
        act_pause.setText("Возобновить трекинг" if paused else "Приостановить трекинг")
        tray.setToolTip("Activity Tracker (Пауза)" if paused else "Activity Tracker — активен")

    act_show.triggered.connect(show_window)
    act_pause.triggered.connect(settings_vm.togglePause)
    act_quit.triggered.connect(quit_app)
    settings_vm.pauseChanged.connect(on_pause_changed)

    tray_menu.addAction(act_show)
    tray_menu.addAction(act_pause)
    tray_menu.addSeparator()
    tray_menu.addAction(act_quit)

    tray.setContextMenu(tray_menu)
    tray.activated.connect(
        lambda reason: show_window()
        if reason
        in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        )
        else None
    )
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()

    def cleanup() -> None:
        tracker.stop()
        db.close()

    app.aboutToQuit.connect(cleanup)
    tracker.start()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())