from __future__ import annotations

import argparse
import json
import os
import platform
import random
import re
import sqlite3
import statistics
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import psutil

ROOT_DIR = Path(__file__).resolve().parent
for candidate in (ROOT_DIR, ROOT_DIR.parent):
    if (candidate / "platform_adapters").is_dir():
        sys.path.insert(0, str(candidate))
        break
    
from platform_adapters import create_platform_adapter


@dataclass
class LivePollingMetrics:
    adapter_name: str
    duration_sec: float
    interval_sec: float
    samples: int
    poll_avg_ms: float
    poll_p95_ms: float
    poll_max_ms: float
    cpu_avg_percent: float
    cpu_peak_percent: float
    ram_avg_mb: float
    ram_peak_mb: float


@dataclass
class StorageCompressionMetrics:
    simulated_days: int
    total_ticks: int
    naive_rows: int
    merged_rows: int
    row_compression_ratio: float
    naive_db_size_mb: float
    merged_db_size_mb: float
    size_reduction_percent: float
    merged_write_ticks_per_sec: float


@dataclass
class QueryLatencyMetrics:
    query_name: str
    runs: int
    avg_ms: float
    p95_ms: float
    max_ms: float


@dataclass
class CategorizerMetrics:
    events_count: int
    rules_count: int
    total_ms: float
    events_per_sec: float


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


def benchmark_live_polling(duration_sec: float, interval_sec: float) -> LivePollingMetrics:
    proc = psutil.Process(os.getpid())
    proc.cpu_percent(interval=None)

    qt_app = None
    if sys.platform.startswith("linux"):
        try:
            from PySide6.QtCore import QCoreApplication

            qt_app = QCoreApplication.instance() or QCoreApplication(sys.argv)
        except Exception:
            qt_app = None

    adapter = create_platform_adapter()
    latencies_ms: list[float] = []
    cpu_samples: list[float] = []
    ram_samples_mb: list[float] = []

    start = time.perf_counter()
    try:
        while (time.perf_counter() - start) < duration_sec:
            if qt_app is not None:
                qt_app.processEvents()

            t0 = time.perf_counter()
            _ = adapter.get_active_window()
            _ = adapter.get_idle_seconds()
            t1 = time.perf_counter()

            latencies_ms.append((t1 - t0) * 1000.0)
            cpu_samples.append(proc.cpu_percent(interval=None))
            ram_samples_mb.append(proc.memory_info().rss / (1024 * 1024))

            elapsed_iter = time.perf_counter() - t0
            sleep_for = max(0.0, interval_sec - elapsed_iter)
            if sleep_for > 0:
                time.sleep(sleep_for)
    finally:
        adapter_name = adapter.adapter_name
        adapter.close()

    valid_cpu = cpu_samples[1:] if len(cpu_samples) > 1 else cpu_samples

    return LivePollingMetrics(
        adapter_name=adapter_name,
        duration_sec=round(time.perf_counter() - start, 2),
        interval_sec=interval_sec,
        samples=len(latencies_ms),
        poll_avg_ms=round(statistics.mean(latencies_ms), 3),
        poll_p95_ms=round(percentile(latencies_ms, 95), 3),
        poll_max_ms=round(max(latencies_ms), 3),
        cpu_avg_percent=round(statistics.mean(valid_cpu), 2),
        cpu_peak_percent=round(max(valid_cpu), 2),
        ram_avg_mb=round(statistics.mean(ram_samples_mb), 2),
        ram_peak_mb=round(max(ram_samples_mb), 2),
    )


_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL,
    productivity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE activity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_name TEXT NOT NULL,
    window_title TEXT NOT NULL,
    start_ts REAL NOT NULL,
    end_ts REAL NOT NULL,
    is_afk INTEGER NOT NULL DEFAULT 0,
    category_id INTEGER REFERENCES categories(id)
);

CREATE INDEX idx_events_start_end ON activity_events(start_ts, end_ts);
CREATE INDEX idx_events_category ON activity_events(category_id);
"""

_SAMPLE_SESSIONS = [
    ("1cv8c", "1С:Предприятие — 1С:Агрокомплекс — Учёт ГСМ и путевых листов", 1),
    ("scalc", "Сводка_урожайности_2026.xlsx — LibreOffice Calc", 1),
    ("qgis-bin", "QGIS 3.38 — Карта полей и индексы NDVI (Отделение №2)", 2),
    ("firefox", "АгроСигнал — Телеметрия техники и выработка — Mozilla Firefox", 2),
    ("firefox", "ФГИС «Зерно» — Оформление СДИЗ на партию пшеницы — Mozilla Firefox", 3),
    ("firefox", "ФГИС «Сатурн» — Журнал применения СЗР — Mozilla Firefox", 3),
    ("firefox", "ВетИС.Меркурий — Ветеринарные сопроводительные документы — Mozilla Firefox", 3),
    ("swriter", "Договор_поставки_удобрений.docx — LibreOffice Writer", 4),
    ("thunderbird", "Входящие — Диспетчерская служба АПК — Mozilla Thunderbird", 4),
    ("telegram-desktop", "Telegram — Чат агрономов", 4),
    ("firefox", "YouTube — Новостная лента — Mozilla Firefox", 5),
    ("firefox", "ВКонтакте — Лента новостей — Mozilla Firefox", 5),
]


def _generate_synthetic_sessions(
    days: int, active_hours_per_day: int = 8, seed: int = 42
) -> list[tuple[str, str, float, float, int, int]]:
    rng = random.Random(seed)
    base_ts = 1_760_000_000.0
    sessions: list[tuple[str, str, float, float, int, int]] = []

    for day in range(days):
        cursor = base_ts + day * 86400 + 8 * 3600
        day_end = cursor + active_hours_per_day * 3600
        while cursor < day_end:
            is_afk = 1 if rng.random() < 0.12 else 0
            if is_afk:
                dur = rng.randint(60, 420)
                app, title, cat_id = "AFK", "Нет активности", 6
            else:
                dur = rng.randint(20, 240)
                app, title, cat_id = rng.choice(_SAMPLE_SESSIONS)
            end = min(cursor + dur, day_end)
            sessions.append((app, title, cursor, end, is_afk, cat_id))
            cursor = end

    return sessions


def _init_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA_SQL)
    conn.executemany(
        "INSERT INTO categories(id, name, color, productivity) VALUES (?, ?, ?, ?)",
        [
            (1, "Учёт и ERP", "#38bdf8", 1),
            (2, "ГИС и точное земледелие", "#34d399", 1),
            (3, "ФГИС и госсистемы АПК", "#818cf8", 1),
            (4, "Документооборот и связь", "#fbbf24", 0),
            (5, "Отвлечения", "#f87171", -1),
            (6, "Простой (AFK)", "#6b7280", 0),
        ],
    )
    conn.commit()
    return conn


def benchmark_storage_and_queries(
    days: int,
) -> tuple[StorageCompressionMetrics, list[QueryLatencyMetrics]]:
    sessions = _generate_synthetic_sessions(days=days)
    total_ticks = int(sum(end - start for _, _, start, end, _, _ in sessions))

    with tempfile.TemporaryDirectory(prefix="activity_bench_") as tmpdir:
        tmp = Path(tmpdir)
        naive_path = tmp / "naive.db"
        merged_path = tmp / "merged.db"

        naive_days = min(days, 7)
        naive_sessions = _generate_synthetic_sessions(days=naive_days)
        naive_ticks = int(sum(end - start for _, _, start, end, _, _ in naive_sessions))

        naive_conn = _init_db(naive_path)
        naive_batch: list[tuple[str, str, float, float, int, int]] = []
        for app, title, s_ts, e_ts, afk, cat_id in naive_sessions:
            t = s_ts
            while t < e_ts:
                naive_batch.append((app, title, t, t + 1.0, afk, cat_id))
                t += 1.0
                if len(naive_batch) >= 20_000:
                    naive_conn.executemany(
                        "INSERT INTO activity_events(app_name, window_title, start_ts, end_ts, is_afk, category_id) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        naive_batch,
                    )
                    naive_batch.clear()
        if naive_batch:
            naive_conn.executemany(
                "INSERT INTO activity_events(app_name, window_title, start_ts, end_ts, is_afk, category_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                naive_batch,
            )
        naive_conn.commit()
        naive_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        naive_conn.close()

        scale_factor = total_ticks / max(1, naive_ticks)
        naive_size_mb = (naive_path.stat().st_size / (1024 * 1024)) * scale_factor

        merged_conn = _init_db(merged_path)
        t_write_start = time.perf_counter()
        cur = merged_conn.cursor()

        cur.execute("BEGIN")
        for app, title, s_ts, e_ts, afk, cat_id in sessions:
            cur.execute(
                "INSERT INTO activity_events(app_name, window_title, start_ts, end_ts, is_afk, category_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (app, title, s_ts, s_ts + 1.0, afk, cat_id),
            )
            row_id = cur.lastrowid
            cur.execute(
                "UPDATE activity_events SET end_ts = ? WHERE id = ?",
                (e_ts, row_id),
            )
        merged_conn.commit()
        write_elapsed = time.perf_counter() - t_write_start

        merged_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        merged_size_mb = merged_path.stat().st_size / (1024 * 1024)
        merged_rows = len(sessions)

        compression = StorageCompressionMetrics(
            simulated_days=days,
            total_ticks=total_ticks,
            naive_rows=total_ticks,
            merged_rows=merged_rows,
            row_compression_ratio=round(total_ticks / max(1, merged_rows), 2),
            naive_db_size_mb=round(naive_size_mb, 2),
            merged_db_size_mb=round(merged_size_mb, 2),
            size_reduction_percent=round(
                (1.0 - merged_size_mb / max(1e-6, naive_size_mb)) * 100.0, 2
            ),
            merged_write_ticks_per_sec=round(total_ticks / max(1e-6, write_elapsed), 1),
        )

        last_ts = sessions[-1][3]
        day_start = last_ts - 86400
        week_start = last_ts - 7 * 86400
        month_start = last_ts - days * 86400

        queries: list[tuple[str, Callable[[], None]]] = [
            (
                "Агрегация по категориям (1 день)",
                lambda: merged_conn.execute(
                    """
                    SELECT c.name, SUM(MIN(e.end_ts, ?) - MAX(e.start_ts, ?))
                    FROM activity_events e
                    LEFT JOIN categories c ON c.id = e.category_id
                    WHERE e.end_ts > ? AND e.start_ts < ? AND e.is_afk = 0
                    GROUP BY e.category_id
                    """,
                    (last_ts, day_start, day_start, last_ts),
                ).fetchall(),
            ),
            (
                "Топ-10 приложений (7 дней)",
                lambda: merged_conn.execute(
                    """
                    SELECT app_name, SUM(MIN(end_ts, ?) - MAX(start_ts, ?)) AS dur
                    FROM activity_events
                    WHERE end_ts > ? AND start_ts < ? AND is_afk = 0
                    GROUP BY app_name
                    ORDER BY dur DESC
                    LIMIT 10
                    """,
                    (last_ts, week_start, week_start, last_ts),
                ).fetchall(),
            ),
            (
                "Сводка по категориям (30 дней)",
                lambda: merged_conn.execute(
                    """
                    SELECT c.name, c.productivity, SUM(end_ts - start_ts)
                    FROM activity_events e
                    LEFT JOIN categories c ON c.id = e.category_id
                    WHERE e.end_ts > ? AND e.start_ts < ? AND e.is_afk = 0
                    GROUP BY e.category_id
                    """,
                    (month_start, last_ts),
                ).fetchall(),
            ),
            (
                "Выборка ленты таймлайна (1 день)",
                lambda: merged_conn.execute(
                    """
                    SELECT app_name, window_title, start_ts, end_ts, is_afk, category_id
                    FROM activity_events
                    WHERE end_ts > ? AND start_ts < ?
                    ORDER BY start_ts ASC
                    """,
                    (day_start, last_ts),
                ).fetchall(),
            ),
        ]

        query_metrics: list[QueryLatencyMetrics] = []
        runs = 50
        for name, fn in queries:
            fn()
            times_ms: list[float] = []
            for _ in range(runs):
                t0 = time.perf_counter()
                fn()
                times_ms.append((time.perf_counter() - t0) * 1000.0)
            query_metrics.append(
                QueryLatencyMetrics(
                    query_name=name,
                    runs=runs,
                    avg_ms=round(statistics.mean(times_ms), 3),
                    p95_ms=round(percentile(times_ms, 95), 3),
                    max_ms=round(max(times_ms), 3),
                )
            )

        merged_conn.close()
        return compression, query_metrics


def benchmark_categorizer(events_count: int = 10_000) -> CategorizerMetrics:
    raw_rules = [
        ("app", r"^(1cv8|1cv8c|1cv8s)(\.exe)?$", True, 1),
        ("app", r"^(excel|scalc|et)(\.exe)?$", True, 1),
        ("title", r"(1с:агрокомплекс|1с:бухгалтерия|урожайность|путевых\s*листов)", True, 1),
        ("app", r"^(qgis|qgis-bin|arcgispro|nextgis)(\.exe)?$", True, 2),
        ("title", r"(агросигнал|cropio|exactfarming|агромон|история\s*поля|ndvi)", True, 2),
        ("title", r"(фгис\s*[«\"]?зерно|фгис\s*[«\"]?сатурн|меркурий|ветис|ефис\s*зсн)", True, 3),
        ("app", "swriter", False, 4),
        ("app", "winword", False, 4),
        ("app", "thunderbird", False, 4),
        ("app", "telegram", False, 4),
        ("title", r"(youtube|вконтакте|vk\.com|twitch|rutube|kinopoisk)", True, 5),
        ("app", "steam", False, 5),
    ] + [("title", f"agro_division_report_{i}", False, 4) for i in range(13)]

    compiled = [
        (field, re.compile(pat, re.IGNORECASE) if is_re else pat.lower(), is_re, cat)
        for field, pat, is_re, cat in raw_rules
    ]

    rng = random.Random(42)
    samples = [rng.choice(_SAMPLE_SESSIONS)[:2] for _ in range(events_count)]

    t0 = time.perf_counter()
    for app, title in samples:
        app_l = app.lower()
        title_l = title.lower()
        for field, matcher, is_re, _ in compiled:
            target = app_l if field == "app" else title_l
            if is_re:
                if matcher.search(target):
                    break
            else:
                if matcher in target:
                    break
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return CategorizerMetrics(
        events_count=events_count,
        rules_count=len(compiled),
        total_ms=round(elapsed_ms, 2),
        events_per_sec=round(events_count / (elapsed_ms / 1000.0), 1),
    )


def build_latex_table(
    live: LivePollingMetrics,
    storage: StorageCompressionMetrics,
    queries: list[QueryLatencyMetrics],
    cat: CategorizerMetrics,
) -> str:
    q_day = queries[0].avg_ms
    q_month = queries[2].avg_ms
    return rf"""\begin{{table}}[htbp]
\centering
\caption{{Результаты нагрузочного тестирования прототипа для рабочих мест АПК ({live.adapter_name})}}
\label{{tab:benchmark_results}}
\begin{{tabular}}{{|l|r|}}
\hline
\textbf{{Показатель}} & \textbf{{Значение}} \\ \hline
Среднее время опроса активного окна и AFK, мс & {live.poll_avg_ms} \\ \hline
95-й перцентиль времени опроса, мс & {live.poll_p95_ms} \\ \hline
Средняя загрузка CPU в фоновом режиме, \% & {live.cpu_avg_percent} \\ \hline
Потребление оперативной памяти (RSS), МБ & {live.ram_avg_mb} \\ \hline
Коэффициент сжатия строк (heartbeat за {storage.simulated_days} дн.) & {storage.row_compression_ratio}$\times$ \\ \hline
Размер БД без склейки / со склейкой, МБ & {storage.naive_db_size_mb} / {storage.merged_db_size_mb} \\ \hline
Снижение объёма хранилища, \% & {storage.size_reduction_percent} \\ \hline
Время агрегации статистики за 1 день (avg), мс & {q_day} \\ \hline
Время агрегации статистики за {storage.simulated_days} дней (avg), мс & {q_month} \\ \hline
Скорость категоризации ({cat.rules_count} правил), соб./с & {cat.events_per_sec:.0f} \\ \hline
\end{{tabular}}
\end{{table}}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Бенчмарк Activity Tracker (АПК)")
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--output", type=Path, default=Path("benchmark_report.json"))
    args = parser.parse_args()

    print(f"[1/4] Живой замер адаптера ({args.duration:.0f} сек, шаг {args.interval} сек)...")
    live = benchmark_live_polling(args.duration, args.interval)

    print(f"[2/4] Тест сжатия БД SQLite ({args.days} дн.) и аналитических запросов...")
    storage, queries = benchmark_storage_and_queries(args.days)

    print("[3/4] Тест скорости категоризатора (10 000 событий)...")
    cat = benchmark_categorizer(10_000)

    print("[4/4] Сохранение результатов...\n")

    report = {
        "system": {
            "os": platform.platform(),
            "python": platform.python_version(),
            "cpu_count_logical": os.cpu_count(),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        },
        "live_polling": asdict(live),
        "storage_compression": asdict(storage),
        "query_latencies": [asdict(q) for q in queries],
        "categorizer": asdict(cat),
    }

    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    tex_path = args.output.with_suffix(".tex")
    tex_path.write_text(build_latex_table(live, storage, queries, cat), encoding="utf-8")

    print("=== СВОДКА БЕНЧМАРКА (ПРОФИЛЬ АПК) ===")
    print(f"Адаптер:          {live.adapter_name}")
    print(f"Опрос окна/AFK:   avg {live.poll_avg_ms} мс | p95 {live.poll_p95_ms} мс | max {live.poll_max_ms} мс")
    print(f"Нагрузка:         CPU avg {live.cpu_avg_percent}% (пик {live.cpu_peak_percent}%) | RAM {live.ram_avg_mb} МБ")
    print(
        f"Heartbeat-сжатие: {storage.naive_rows:,} -> {storage.merged_rows:,} строк "
        f"({storage.row_compression_ratio}x) | {storage.naive_db_size_mb} МБ -> {storage.merged_db_size_mb} МБ "
        f"(-{storage.size_reduction_percent}%)"
    )
    print("SQL-запросы (50 прогонов):")
    for q in queries:
        print(f"  • {q.query_name:<35} avg {q.avg_ms:>6} мс | p95 {q.p95_ms:>6} мс")
    print(f"Категоризатор:    {cat.events_count} событий за {cat.total_ms} мс ({cat.events_per_sec:,.0f} соб./с)")
    print(f"\nСохранено: {args.output} и {tex_path}")


if __name__ == "__main__":
    main()