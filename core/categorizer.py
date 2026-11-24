import re
import threading
from dataclasses import dataclass
from typing import Iterable, Optional

from .models import Rule


@dataclass(slots=True)
class _CompiledRule:
    rule: Rule
    regex: Optional[re.Pattern[str]]
    needle_lower: str


class ActivityCategorizer:
    """Движок классификации событий активности по приоритетным правилам."""

    def __init__(self, rules: Iterable[Rule] = ()) -> None:
        self._lock = threading.RLock()
        self._compiled: list[_CompiledRule] = []
        self.reload_rules(rules)

    def reload_rules(self, rules: Iterable[Rule]) -> None:
        """Пересобирает кэш правил, сортируя их по возрастанию priority."""
        sorted_rules = sorted(rules, key=lambda r: (r.priority, r.id or 0))
        compiled: list[_CompiledRule] = []

        for rule in sorted_rules:
            pattern_str = rule.pattern.strip()
            if not pattern_str:
                continue

            if rule.is_regex:
                try:
                    regex = re.compile(pattern_str, re.IGNORECASE)
                except re.error:
                    continue
                compiled.append(_CompiledRule(rule=rule, regex=regex, needle_lower=""))
            else:
                compiled.append(
                    _CompiledRule(rule=rule, regex=None, needle_lower=pattern_str.lower())
                )

        with self._lock:
            self._compiled = compiled

    def classify(self, app_name: str, window_title: str) -> Optional[int]:
        """Возвращает category_id первого сработавшего правила или None."""
        app_str = app_name or ""
        title_str = window_title or ""
        app_lower = app_str.lower()
        title_lower = title_str.lower()

        with self._lock:
            rules_snapshot = list(self._compiled)

        for item in rules_snapshot:
            field = item.rule.match_field
            if item.regex is not None:
                target = app_str if field == "app_name" else title_str
                if item.regex.search(target):
                    return item.rule.category_id
            else:
                target_lower = app_lower if field == "app_name" else title_lower
                if item.needle_lower in target_lower:
                    return item.rule.category_id

        return None