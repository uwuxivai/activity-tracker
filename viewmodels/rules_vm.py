import re
import sqlite3
from typing import Optional

from PySide6.QtCore import Property, QObject, Signal, Slot

from core import ActivityCategorizer, ActivityDatabase


class RulesVM(QObject):
    """ViewModel управления категориями, правилами классификации и пересчётом истории."""

    dataChanged = Signal()
    statusChanged = Signal()
    rulesUpdated = Signal()

    def __init__(
        self,
        db: ActivityDatabase,
        categorizer: ActivityCategorizer,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._categorizer = categorizer
        self._categories: list[dict] = []
        self._rules: list[dict] = []
        self._status_message = ""
        self.refresh()

    def _set_status(self, message: str) -> None:
        self._status_message = message
        self.statusChanged.emit()

    @Slot()
    def refresh(self) -> None:
        cats = self._db.get_categories()
        cat_map = {c.id: c for c in cats if c.id is not None}

        prod_labels = {1: "Продуктивно", 0: "Нейтрально", -1: "Отвлекает"}
        self._categories = [
            {
                "id": c.id,
                "name": c.name,
                "color": c.color,
                "productivity": c.productivity,
                "productivityLabel": prod_labels.get(c.productivity, "Нейтрально"),
            }
            for c in cats
        ]

        rules = self._db.get_rules()
        self._rules = [
            {
                "id": r.id,
                "pattern": r.pattern,
                "matchField": r.match_field,
                "matchFieldLabel": "Приложение" if r.match_field == "app_name" else "Заголовок окна",
                "isRegex": r.is_regex,
                "priority": r.priority,
                "categoryId": r.category_id,
                "categoryName": cat_map[r.category_id].name if r.category_id in cat_map else "—",
                "categoryColor": cat_map[r.category_id].color if r.category_id in cat_map else "#64748b",
            }
            for r in rules
        ]
        self.dataChanged.emit()

    @Slot(str, str, int)
    def addCategory(self, name: str, color: str, productivity: int) -> None:
        clean_name = name.strip()
        if not clean_name:
            self._set_status("Введите название категории.")
            return
        try:
            self._db.add_category(clean_name, color or "#3b82f6", productivity)
            self.refresh()
            self.rulesUpdated.emit()
            self._set_status(f"Категория «{clean_name}» добавлена.")
        except sqlite3.IntegrityError:
            self._set_status(f"Категория «{clean_name}» уже существует.")

    @Slot(int)
    def deleteCategory(self, category_id: int) -> None:
        self._db.delete_category(category_id)
        self.refresh()
        self.rulesUpdated.emit()
        self._set_status("Категория удалена.")

    @Slot(str, str, int, bool, int)
    def addRule(
        self,
        pattern: str,
        match_field: str,
        category_id: int,
        is_regex: bool,
        priority: int,
    ) -> None:
        clean_pattern = pattern.strip()
        if not clean_pattern:
            self._set_status("Введите шаблон поиска.")
            return
        if category_id <= 0:
            self._set_status("Выберите категорию для правила.")
            return
        if is_regex:
            try:
                re.compile(clean_pattern)
            except re.error as err:
                self._set_status(f"Ошибка регулярного выражения: {err}")
                return

        self._db.add_rule(clean_pattern, match_field, category_id, is_regex, priority)
        self.refresh()
        self.rulesUpdated.emit()
        self._set_status(f"Правило «{clean_pattern}» добавлено.")

    @Slot(int)
    def deleteRule(self, rule_id: int) -> None:
        self._db.delete_rule(rule_id)
        self.refresh()
        self.rulesUpdated.emit()
        self._set_status("Правило удалено.")

    @Slot()
    def recategorizeHistory(self) -> None:
        self._categorizer.reload_rules(self._db.get_rules())
        updated = self._db.recategorize_all(self._categorizer)
        self.rulesUpdated.emit()
        self._set_status(f"Пересчёт завершён: обновлено записей — {updated}.")

    @Property("QVariantList", notify=dataChanged)
    def categories(self) -> list[dict]:
        return self._categories

    @Property("QVariantList", notify=dataChanged)
    def rules(self) -> list[dict]:
        return self._rules

    @Property(str, notify=statusChanged)
    def statusMessage(self) -> str:
        return self._status_message