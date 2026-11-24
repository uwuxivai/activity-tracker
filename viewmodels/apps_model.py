from typing import Any

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, Qt

from core.models import AppStat


def _fmt_short(seconds: float) -> str:
    sec = int(round(max(0.0, seconds)))
    hours, rem = divmod(sec, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours} ч {minutes:02d} мин"
    if minutes > 0:
        return f"{minutes} мин {secs:02d} с"
    return f"{secs} с"


class AppsListModel(QAbstractListModel):
    """Модель списка топ-приложений для QML ListView."""

    AppNameRole = Qt.ItemDataRole.UserRole + 1
    DurationTextRole = Qt.ItemDataRole.UserRole + 2
    TotalSecondsRole = Qt.ItemDataRole.UserRole + 3
    SharePercentRole = Qt.ItemDataRole.UserRole + 4
    CategoryNameRole = Qt.ItemDataRole.UserRole + 5
    CategoryColorRole = Qt.ItemDataRole.UserRole + 6

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[AppStat] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None

        item = self._items[index.row()]
        if role == self.AppNameRole:
            return item.app_name
        if role == self.DurationTextRole:
            return _fmt_short(item.total_seconds)
        if role == self.TotalSecondsRole:
            return item.total_seconds
        if role == self.SharePercentRole:
            return item.share_percent
        if role == self.CategoryNameRole:
            return item.category_name
        if role == self.CategoryColorRole:
            return item.category_color
        return None

    def roleNames(self) -> dict[int, QByteArray]:  # noqa: N802
        return {
            self.AppNameRole: QByteArray(b"appName"),
            self.DurationTextRole: QByteArray(b"durationText"),
            self.TotalSecondsRole: QByteArray(b"totalSeconds"),
            self.SharePercentRole: QByteArray(b"sharePercent"),
            self.CategoryNameRole: QByteArray(b"categoryName"),
            self.CategoryColorRole: QByteArray(b"categoryColor"),
        }

    def set_items(self, items: list[AppStat]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()