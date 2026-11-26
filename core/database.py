import csv
import json
import sqlite3
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from .categorizer import ActivityCategorizer
from .models import (
    ActivityEvent,
    AppStat,
    Category,
    CategoryStat,
    HourlyStat,
    PeriodStats,
    Rule,
)

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#64748b',
    productivity INTEGER NOT NULL DEFAULT 0 CHECK (productivity IN (-1, 0, 1))
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    match_field TEXT NOT NULL CHECK (match_field IN ('app_name', 'window_title')),
    is_regex INTEGER NOT NULL DEFAULT 0,
    priority INTEGER NOT NULL DEFAULT 100,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT NOT NULL,
    window_title TEXT NOT NULL,
    start_ts REAL NOT NULL,
    end_ts REAL NOT NULL,
    is_afk INTEGER NOT NULL DEFAULT 0,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_time ON activity_events(start_ts, end_ts);
CREATE INDEX IF NOT EXISTS idx_events_afk ON activity_events(is_afk, start_ts);
CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority, id);
"""

DEFAULT_CATEGORIES: list[tuple[str, str, int]] = [
    ("Учёт и ERP", "#38bdf8", 1),
    ("ГИС и точное земледелие", "#34d399", 1),
    ("ФГИС и госсистемы АПК", "#818cf8", 1),
    ("Документооборот и связь", "#fbbf24", 0),
    ("Отвлечения", "#f87171", -1),
    ("Без категории", "#6b7280", 0),
]

DEFAULT_RULES: list[tuple[str, str, int, int, str]] = [
    (r"^(1cv8|1cv8c|1cv8s)(\.exe)?$", "app_name", 1, 100, "Учёт и ERP"),
    (r"^(excel|scalc|et)(\.exe)?$", "app_name", 1, 90, "Учёт и ERP"),
    (r"(1с:предприятие|1с:агрокомплекс|1с:бухгалтерия|сводка|ведомость|урожайность)", "window_title", 1, 85, "Учёт и ERP"),

    (r"^(qgis|qgis-bin|qgis-ltr-bin|arcgispro|nextgis)(\.exe)?$", "app_name", 1, 100, "ГИС и точное земледелие"),
    (r"(агросигнал|agrosignal|cropio|exactfarming|агромон|agromon|история\s*поля|historyfield|ndvi|карта\s*полей)", "window_title", 1, 95, "ГИС и точное земледелие"),

    (r"(фгис\s*[«\"]?зерно|фгис\s*[«\"]?сатурн|меркурий|ветис|ефис\s*зсн|фгис\s*семеноводство|госуслуги|минсельхоз)", "window_title", 1, 98, "ФГИС и госсистемы АПК"),

    (r"^(winword|swriter|soffice\.bin|okular|evince|acrobat|acrord32)(\.exe)?$", "app_name", 1, 70, "Документооборот и связь"),
    (r"^(thunderbird|outlook|telegram|telegram-desktop|mattermost|yandex-telemost/max)(\.exe)?$", "app_name", 1, 65, "Документооборот и связь"),
    (r"(диадок|сбис|почта|mail\.ru|яндекс\.почта|max\.ru|\.(docx|odt|pdf|xlsx|ods))", "window_title", 1, 60, "Документооборот и связь"),

    (r"(youtube|vk\.com|вконтакте|twitch|rutube|kinopoisk|pikabu|ok\.ru)", "window_title", 1, 96, "Отвлечения"),
    (r"^(steam|epicgameslauncher|discord)(\.exe)?$", "app_name", 1, 92, "Отвлечения"),
]


class ActivityDatabase:
    """Потокобезопасный слой хранения SQLite с WAL, heartbeat-склейкой и аналитикой."""

    def __init__(self, db_path: str | Path = "activity_tracker.db") -> None:
        self._db_path = str(db_path)
        if self._db_path != ":memory:":
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON;")
            if self._db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL;")
                self._conn.execute("PRAGMA synchronous = NORMAL;")
            self._conn.execute("PRAGMA busy_timeout = 5000;")
            self._conn.executescript(_SCHEMA_SQL)
            self._seed_defaults_if_empty()
            self._conn.commit()

    def _seed_defaults(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            count = cur.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
            if count > 0:
                return

            cur.executemany(
                "INSERT INTO categories(name, color, productivity) VALUES (?, ?, ?)",
                DEFAULT_CATEGORIES,
            )
            cat_map = {
                row[1]: row[0]
                for row in cur.execute("SELECT id, name FROM categories").fetchall()
            }
            cur.executemany(
                """
                INSERT INTO rules(pattern, match_field, is_regex, priority, category_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (pat, field, is_re, prio, cat_map[cat_name])
                    for pat, field, is_re, prio, cat_name in DEFAULT_RULES
                    if cat_name in cat_map
                ],
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def record_heartbeat(
        self,
        app_name: str,
        window_title: str,
        timestamp: float,
        step_seconds: float,
        is_afk: bool,
        category_id: Optional[int],
        pulse_timeout: float = 5.0,
    ) -> int:
        norm_app = "AFK" if is_afk else (app_name or "unknown")
        norm_title = "Пользователь неактивен" if is_afk else (window_title or "")
        effective_cat = None if is_afk else category_id
        afk_int = 1 if is_afk else 0

        with self._lock:
            last = self._conn.execute(
                """
                SELECT id, app_name, window_title, start_ts, end_ts, is_afk
                FROM activity_events
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            if last is not None:
                gap = timestamp - float(last["end_ts"])
                same_state = (
                    last["app_name"] == norm_app
                    and last["window_title"] == norm_title
                    and int(last["is_afk"]) == afk_int
                )
                if same_state and 0.0 <= gap <= pulse_timeout:
                    new_end = max(float(last["end_ts"]), timestamp)
                    self._conn.execute(
                        "UPDATE activity_events SET end_ts = ?, category_id = ? WHERE id = ?",
                        (new_end, effective_cat, last["id"]),
                    )
                    self._conn.commit()
                    return int(last["id"])

            start_ts = max(0.0, timestamp - max(0.1, step_seconds))
            if last is not None and start_ts < float(last["end_ts"]) <= timestamp:
                start_ts = float(last["end_ts"])

            cur = self._conn.execute(
                """
                INSERT INTO activity_events
                    (app_name, window_title, start_ts, end_ts, is_afk, category_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (norm_app, norm_title, start_ts, timestamp, afk_int, effective_cat),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def get_categories(self) -> list[Category]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, name, color, productivity FROM categories ORDER BY id ASC"
            ).fetchall()
        return [
            Category(
                id=int(r["id"]),
                name=str(r["name"]),
                color=str(r["color"]),
                productivity=int(r["productivity"]),
            )
            for r in rows
        ]

    def add_category(self, name: str, color: str = "#64748b", productivity: int = 0) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO categories (name, color, productivity) VALUES (?, ?, ?)",
                (name.strip(), color, int(productivity)),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def update_category(self, category_id: int, name: str, color: str, productivity: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE categories SET name = ?, color = ?, productivity = ? WHERE id = ?",
                (name.strip(), color, int(productivity), category_id),
            )
            self._conn.commit()

    def delete_category(self, category_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
            self._conn.commit()

    def get_rules(self) -> list[Rule]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, pattern, match_field, is_regex, priority, category_id
                FROM rules
                ORDER BY priority ASC, id ASC
                """
            ).fetchall()
        return [
            Rule(
                id=int(r["id"]),
                pattern=str(r["pattern"]),
                match_field=str(r["match_field"]),
                is_regex=bool(r["is_regex"]),
                priority=int(r["priority"]),
                category_id=int(r["category_id"]),
            )
            for r in rows
        ]

    def add_rule(
        self,
        pattern: str,
        match_field: str,
        category_id: int,
        is_regex: bool = False,
        priority: int = 100,
    ) -> int:
        with self._lock:
            cur = self._conn.execute(
                """
                INSERT INTO rules (pattern, match_field, is_regex, priority, category_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (pattern.strip(), match_field, int(is_regex), int(priority), category_id),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def delete_rule(self, rule_id: int) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
            self._conn.commit()

    def recategorize_all(self, categorizer: ActivityCategorizer) -> int:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, app_name, window_title, category_id FROM activity_events WHERE is_afk = 0"
            ).fetchall()

            updates: list[tuple[Optional[int], int]] = []
            for row in rows:
                new_cat = categorizer.classify(row["app_name"], row["window_title"])
                if new_cat != row["category_id"]:
                    updates.append((new_cat, int(row["id"])))

            if updates:
                self._conn.executemany(
                    "UPDATE activity_events SET category_id = ? WHERE id = ?",
                    updates,
                )
                self._conn.commit()
            return len(updates)

    def get_setting(self, key: str, default: str = "") -> str:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM settings WHERE key = ?", (key,)
            ).fetchone()
        return str(row["value"]) if row is not None else default

    def set_setting(self, key: str, value: str) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )
            self._conn.commit()

    def get_events_in_range(self, start_ts: float, end_ts: float) -> list[ActivityEvent]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT
                    e.id,
                    e.app_name,
                    e.window_title,
                    MAX(e.start_ts, ?) AS clipped_start,
                    MIN(e.end_ts, ?)   AS clipped_end,
                    e.is_afk,
                    e.category_id,
                    COALESCE(c.name, 'Без категории') AS category_name,
                    COALESCE(c.color, '#64748b')      AS category_color,
                    COALESCE(c.productivity, 0)       AS productivity
                FROM activity_events e
                LEFT JOIN categories c ON c.id = e.category_id
                WHERE e.end_ts > ? AND e.start_ts < ?
                ORDER BY clipped_start ASC
                """,
                (start_ts, end_ts, start_ts, end_ts),
            ).fetchall()

        return [
            ActivityEvent(
                id=int(r["id"]),
                app_name=str(r["app_name"]),
                window_title=str(r["window_title"]),
                start_ts=float(r["clipped_start"]),
                end_ts=float(r["clipped_end"]),
                is_afk=bool(r["is_afk"]),
                category_id=int(r["category_id"]) if r["category_id"] is not None else None,
                category_name="AFK" if r["is_afk"] else str(r["category_name"]),
                category_color="#475569" if r["is_afk"] else str(r["category_color"]),
                productivity=int(r["productivity"]),
            )
            for r in rows
            if float(r["clipped_end"]) > float(r["clipped_start"])
        ]

    def get_period_stats(
        self,
        start_ts: float,
        end_ts: float,
        top_limit: int = 10,
    ) -> PeriodStats:
        events = self.get_events_in_range(start_ts, end_ts)

        active_sec = 0.0
        afk_sec = 0.0
        prod_sec = 0.0
        neutral_sec = 0.0
        distract_sec = 0.0

        app_totals: dict[str, float] = defaultdict(float)
        app_meta: dict[str, tuple[str, str]] = {}
        cat_totals: dict[Optional[int], float] = defaultdict(float)
        cat_meta: dict[Optional[int], tuple[str, str, int]] = {}
        hourly_buckets = [HourlyStat(hour=h) for h in range(24)]

        for ev in events:
            dur = ev.duration
            if dur <= 0.0:
                continue

            self._distribute_hourly(hourly_buckets, ev)

            if ev.is_afk:
                afk_sec += dur
                continue

            active_sec += dur
            if ev.productivity > 0:
                prod_sec += dur
            elif ev.productivity < 0:
                distract_sec += dur
            else:
                neutral_sec += dur

            app_totals[ev.app_name] += dur
            app_meta[ev.app_name] = (ev.category_name, ev.category_color)

            cat_totals[ev.category_id] += dur
            cat_meta[ev.category_id] = (ev.category_name, ev.category_color, ev.productivity)

        productivity_index = (prod_sec / active_sec * 100.0) if active_sec > 0 else 0.0

        top_apps = [
            AppStat(
                app_name=app,
                total_seconds=round(sec, 2),
                share_percent=round((sec / active_sec * 100.0) if active_sec > 0 else 0.0, 1),
                category_name=app_meta[app][0],
                category_color=app_meta[app][1],
            )
            for app, sec in sorted(app_totals.items(), key=lambda x: x[1], reverse=True)[:top_limit]
        ]

        categories = [
            CategoryStat(
                category_id=cid,
                name=cat_meta[cid][0],
                color=cat_meta[cid][1],
                productivity=cat_meta[cid][2],
                total_seconds=round(sec, 2),
                share_percent=round((sec / active_sec * 100.0) if active_sec > 0 else 0.0, 1),
            )
            for cid, sec in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True)
        ]

        return PeriodStats(
            start_ts=start_ts,
            end_ts=end_ts,
            active_seconds=round(active_sec, 2),
            afk_seconds=round(afk_sec, 2),
            productive_seconds=round(prod_sec, 2),
            neutral_seconds=round(neutral_sec, 2),
            distracting_seconds=round(distract_sec, 2),
            productivity_index=round(productivity_index, 1),
            top_apps=top_apps,
            categories=categories,
            hourly=hourly_buckets,
        )

    @staticmethod
    def _distribute_hourly(buckets: list[HourlyStat], ev: ActivityEvent) -> None:
        cursor = ev.start_ts
        while cursor < ev.end_ts:
            dt = datetime.fromtimestamp(cursor)
            hour = dt.hour
            next_hour_ts = (
                dt.replace(minute=0, second=0, microsecond=0).timestamp() + 3600.0
            )
            slice_end = min(ev.end_ts, next_hour_ts)
            chunk = max(0.0, slice_end - cursor)

            if ev.is_afk:
                buckets[hour].afk_seconds += chunk
            else:
                buckets[hour].active_seconds += chunk
                if ev.productivity > 0:
                    buckets[hour].productive_seconds += chunk

            cursor = slice_end if slice_end > cursor else ev.end_ts

    def export_csv(self, filepath: str | Path, start_ts: float, end_ts: float) -> int:
        events = self.get_events_in_range(start_ts, end_ts)
        out_path = Path(filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        with out_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(
                [
                    "id",
                    "start_iso",
                    "end_iso",
                    "duration_sec",
                    "app_name",
                    "window_title",
                    "is_afk",
                    "category",
                    "productivity",
                ]
            )
            for ev in events:
                writer.writerow(
                    [
                        ev.id,
                        datetime.fromtimestamp(ev.start_ts).isoformat(timespec="seconds"),
                        datetime.fromtimestamp(ev.end_ts).isoformat(timespec="seconds"),
                        round(ev.duration, 2),
                        ev.app_name,
                        ev.window_title,
                        int(ev.is_afk),
                        ev.category_name,
                        ev.productivity,
                    ]
                )
        return len(events)

    def export_json(self, filepath: str | Path, start_ts: float, end_ts: float) -> int:
        stats = self.get_period_stats(start_ts, end_ts)
        events = self.get_events_in_range(start_ts, end_ts)
        out_path = Path(filepath)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "period": {
                "start_iso": datetime.fromtimestamp(start_ts).isoformat(timespec="seconds"),
                "end_iso": datetime.fromtimestamp(end_ts).isoformat(timespec="seconds"),
            },
            "summary": {
                "active_seconds": stats.active_seconds,
                "afk_seconds": stats.afk_seconds,
                "productive_seconds": stats.productive_seconds,
                "neutral_seconds": stats.neutral_seconds,
                "distracting_seconds": stats.distracting_seconds,
                "productivity_index": stats.productivity_index,
            },
            "events": [
                {
                    "id": ev.id,
                    "start_ts": ev.start_ts,
                    "end_ts": ev.end_ts,
                    "duration_sec": round(ev.duration, 2),
                    "app_name": ev.app_name,
                    "window_title": ev.window_title,
                    "is_afk": ev.is_afk,
                    "category": ev.category_name,
                    "productivity": ev.productivity,
                }
                for ev in events
            ],
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return len(events)