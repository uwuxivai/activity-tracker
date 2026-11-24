import argparse
import json
import os
import platform
import random
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

import psutil
from PySide6.QtCore import QCoreApplication

# Добавляем корень проекта в sys.path для импорта platform_adapters
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from platform_adapters import create_platform_adapter


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def benchmark_platform_adapter(duration_sec: int, interval_sec: float) -> dict:
    """Замеряет задержки вызовов ОС, CPU и RAM фонового поллинга."""
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    adapter = create_platform_adapter()
    proc = psutil.Process(os.getpid())

    # Прогрев адаптера и счётчика CPU
    proc.cpu_percent(interval=None)
    app.processEvents()
    adapter.get_active_window()
    adapter.get_idle_seconds()

    win_latencies_ms: list[float] = []
    idle_latencies_ms: list[float] = []
    cpu_samples: list[float] = []
    rss_samples_mb: list[float] = []

    steps = max(1, int(duration_sec / interval_sec))
    print(f"[1/3] Замер адаптера '{adapter.adapter_name}': {steps} тиков (интервал {interval_sec} с)...")

    try:
        for _ in range(steps):
            loop_start = time.perf_counter()
            app.processEvents()

            t0 = time.perf_counter()
            adapter.get_active_window()
            t1 = time.perf_counter()
            adapter.get_idle_seconds()
            t2 = time.perf_counter()

            win_latencies_ms.append((t1 - t0) * 1000.0)
            idle_latencies_ms.append((t2 - t1) * 1000.0)

            cpu_samples.append(proc.cpu_percent(interval=None))
            rss_samples_mb.append(proc.memory_info().rss / (1024 * 1024))

            elapsed = time.perf_counter() - loop_start
            sleep_left = max(0.0, interval_sec - elapsed)
            # Небольшими шагами спим, чтобы Qt event loop (D-Bus) оставался живым
            sleep_end = time.perf_counter() + sleep_left
            while time.perf_counter() < sleep_end:
                app.processEvents()
                time.sleep(min(0.05, max(0.0, sleep_end - time.perf_counter())))
    finally:
        adapter.close()

    return {
        "adapter_name": adapter.adapter_name,
        "ticks": steps,
        "interval_sec": interval_sec,
        "window_query_ms": {
            "min": round(min(win_latencies_ms), 3),
            "avg": round(statistics.mean(win_latencies_ms), 3),
            "p95": round(percentile(win_latencies_ms, 95), 3),
            "max": round(max(win_latencies_ms), 3),
        },
        "idle_query_ms": {
            "min": round(min(idle_latencies_ms), 3),
            "avg": round(statistics.mean(idle_latencies_ms), 3),
            "p95": round(percentile(idle_latencies_ms, 95), 3),
            "max": round(max(idle_latencies_ms), 3),
        },
        "headless_cpu_percent": {
            "avg": round(statistics.mean(cpu_samples), 2),
            "max": round(max(cpu_samples), 2),
        },
        "headless_ram_mb": {
            "avg": round(statistics.mean(rss_samples_mb), 2),
            "max": round(max(rss_samples_mb), 2),
        },
    }


def benchmark_running_gui(pid: int, duration_sec: int) -> dict:
    """Снимает CPU и RAM (RSS) с уже запущенного экземпляра main.py (PySide6 + QML)."""
    print(f"[GUI] Мониторинг процесса PID={pid} в течение {duration_sec} с...")
    proc = psutil.Process(pid)
    proc.cpu_percent(interval=None)
    cpu_samples: list[float] = []
    rss_samples_mb: list[float] = []

    for _ in range(max(1, duration_sec)):
        time.sleep(1.0)
        cpu_samples.append(proc.cpu_percent(interval=None))
        rss_samples_mb.append(proc.memory_info().rss / (1024 * 1024))

    return {
        "pid": pid,
        "process_name": proc.name(),
        "gui_cpu_percent": {
            "avg": round(statistics.mean(cpu_samples), 2),
            "max": round(max(cpu_samples), 2),
        },
        "gui_ram_mb": {
            "avg": round(statistics.mean(rss_samples_mb), 2),
            "max": round(max(rss_samples_mb), 2),
        },
    }


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute(
        """
        CREATE TABLE activity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_name TEXT NOT NULL,
            window_title TEXT NOT NULL,
            start_ts REAL NOT NULL,
            end_ts REAL NOT NULL,
            is_afk INTEGER NOT NULL DEFAULT 0,
            category_id INTEGER
        );
        """
    )
    conn.execute("CREATE INDEX idx_events_time ON activity_events(start_ts, end_ts);")
    conn.execute("CREATE INDEX idx_events_cat ON activity_events(category_id);")


def benchmark_database_and_heartbeat(days: int, hours_per_day: int = 8) -> dict:
    """
    Моделирует реалистичный поток переключений окон за N рабочих дней (шаг 1 с).
    Сравнивает запись без склейки (raw ticks) и с heartbeat-склейкой,
    а также замеряет скорость аналитических SQL-запросов.
    """
    print(f"[2/3] Симуляция БД за {days} дн. ({hours_per_day} ч/день, тик = 1 с)...")
    rng = random.Random(42)
    sample_windows = [
        ("code", "main.py — activity_tracker — Visual Studio Code", 1),
        ("code", "HourlyBarChart.qml — activity_tracker — Visual Studio Code", 1),
        ("firefox", "PySide6 QML Documentation — Mozilla Firefox", 1),
        ("firefox", "YouTube — Lo-Fi Hip Hop Radio", 3),
        ("telegram-desktop", "Telegram", 2),
        ("alacritty", "zsh — ~/projects/activity_tracker", 1),
        ("libreoffice", "Курсовая_работа.docx — LibreOffice Writer", 1),
    ]

    total_raw_ticks = days * hours_per_day * 3600
    base_ts = 1_760_000_000.0

    # Генерируем сессии средней длительностью ~95 сек (реалистичное переключение окон)
    merged_rows: list[tuple] = []
    for day in range(days):
        t = base_ts + day * 86400.0 + 9 * 3600.0
        day_end = t + hours_per_day * 3600.0
        while t < day_end:
            is_afk = 1 if rng.random() < 0.08 else 0
            if is_afk:
                dur = float(rng.randint(60, 300))
                app_name, title, cat_id = "AFK", "", 4
            else:
                dur = float(rng.randint(15, 240))
                app_name, title, cat_id = rng.choice(sample_windows)
            end_t = min(day_end, t + dur)
            merged_rows.append((app_name, title, t, end_t, is_afk, cat_id))
            t = end_t

    with tempfile.TemporaryDirectory() as tmpdir:
        merged_db_path = Path(tmpdir) / "merged.db"
        raw_db_path = Path(tmpdir) / "raw_sample.db"

        # 1. Запись с heartbeat-склейкой (все N дней)
        conn = sqlite3.connect(merged_db_path)
        _create_schema(conn)
        t_ins_start = time.perf_counter()
        with conn:
            conn.executemany(
                """
                INSERT INTO activity_events
                    (app_name, window_title, start_ts, end_ts, is_afk, category_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                merged_rows,
            )
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        insert_merged_ms = (time.perf_counter() - t_ins_start) * 1000.0

        # 2. Замер скорости аналитических запросов на 30-дневной БД
        print("[3/3] Замер скорости аналитических SQL-запросов...")
        last_day_start = base_ts + (days - 1) * 86400.0
        last_day_end = last_day_start + 86400.0
        week_start = base_ts + max(0, days - 7) * 86400.0
        month_start = base_ts

        def measure_query(sql: str, params: tuple, runs: int = 30) -> float:
            times = []
            for _ in range(runs):
                t0 = time.perf_counter()
                conn.execute(sql, params).fetchall()
                times.append((time.perf_counter() - t0) * 1000.0)
            return round(statistics.mean(times), 3)

        top_apps_sql = """
            SELECT app_name,
                   SUM(MIN(end_ts, ?) - MAX(start_ts, ?)) AS total_sec
            FROM activity_events
            WHERE end_ts > ? AND start_ts < ? AND is_afk = 0
            GROUP BY app_name
            ORDER BY total_sec DESC
            LIMIT 10;
        """
        cat_sql = """
            SELECT category_id,
                   SUM(MIN(end_ts, ?) - MAX(start_ts, ?)) AS total_sec
            FROM activity_events
            WHERE end_ts > ? AND start_ts < ? AND is_afk = 0
            GROUP BY category_id;
        """
        day_events_sql = """
            SELECT app_name, window_title, start_ts, end_ts, is_afk, category_id
            FROM activity_events
            WHERE end_ts > ? AND start_ts < ?
            ORDER BY start_ts ASC;
        """

        q_day_apps_ms = measure_query(
            top_apps_sql, (last_day_end, last_day_start, last_day_start, last_day_end)
        )
        q_week_apps_ms = measure_query(
            top_apps_sql, (last_day_end, week_start, week_start, last_day_end)
        )
        q_month_apps_ms = measure_query(
            top_apps_sql, (last_day_end, month_start, month_start, last_day_end)
        )
        q_month_cats_ms = measure_query(
            cat_sql, (last_day_end, month_start, month_start, last_day_end)
        )
        q_day_timeline_ms = measure_query(
            day_events_sql, (last_day_start, last_day_end)
        )
        conn.close()

        merged_size_kb = merged_db_path.stat().st_size / 1024.0

        # 3. Оценка размера БД БЕЗ склейки (экстраполяция по 1 полному рабочему дню = 28 800 строк)
        raw_one_day = hours_per_day * 3600
        raw_conn = sqlite3.connect(raw_db_path)
        _create_schema(raw_conn)
        raw_sample_rows = [
            (
                sample_windows[i % len(sample_windows)][0],
                sample_windows[i % len(sample_windows)][1],
                base_ts + i,
                base_ts + i + 1.0,
                0,
                sample_windows[i % len(sample_windows)][2],
            )
            for i in range(raw_one_day)
        ]
        with raw_conn:
            raw_conn.executemany(
                """
                INSERT INTO activity_events
                    (app_name, window_title, start_ts, end_ts, is_afk, category_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                raw_sample_rows,
            )
        raw_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        raw_conn.close()

        raw_one_day_kb = raw_db_path.stat().st_size / 1024.0
        estimated_raw_total_mb = (raw_one_day_kb * days) / 1024.0
        compression_ratio = total_raw_ticks / max(1, len(merged_rows))
        size_reduction_ratio = (raw_one_day_kb * days) / max(0.1, merged_size_kb)

    return {
        "simulated_days": days,
        "hours_per_day": hours_per_day,
        "raw_ticks_total": total_raw_ticks,
        "merged_rows_total": len(merged_rows),
        "row_compression_ratio": round(compression_ratio, 1),
        "merged_db_size_kb": round(merged_size_kb, 1),
        "estimated_raw_db_size_mb": round(estimated_raw_total_mb, 2),
        "size_reduction_ratio": round(size_reduction_ratio, 1),
        "bulk_insert_merged_ms": round(insert_merged_ms, 2),
        "queries_ms": {
            "top_apps_1_day": q_day_apps_ms,
            "top_apps_7_days": q_week_apps_ms,
            "top_apps_30_days": q_month_apps_ms,
            "categories_30_days": q_month_cats_ms,
            "timeline_1_day": q_day_timeline_ms,
        },
    }


def generate_latex_table(report: dict) -> str:
    env = report["environment"]
    ad = report["adapter_benchmark"]
    db = report["database_benchmark"]
    gui = report.get("gui_benchmark")

    rows = [
        f"Платформа / адаптер & {env['os']} ({ad['adapter_name']}) \\\\",
        f"Задержка получения активного окна (avg / p95) & {ad['window_query_ms']['avg']} / {ad['window_query_ms']['p95']} мс \\\\",
        f"Задержка получения времени простоя (avg / p95) & {ad['idle_query_ms']['avg']} / {ad['idle_query_ms']['p95']} мс \\\\",
        f"Нагрузка на CPU (фоновый опрос, avg / max) & {ad['headless_cpu_percent']['avg']} / {ad['headless_cpu_percent']['max']} \\% \\\\",
        f"Потребление RAM (фоновый сервис, avg) & {ad['headless_ram_mb']['avg']} МБ \\\\",
    ]
    if gui:
        rows.append(
            f"Нагрузка на CPU (полное GUI-приложение, avg) & {gui['gui_cpu_percent']['avg']} \\% \\\\"
        )
        rows.append(
            f"Потребление RAM (полное GUI-приложение, avg) & {gui['gui_ram_mb']['avg']} МБ \\\\"
        )
    rows.extend(
        [
            f"Сжатие записей heartbeat ({db['simulated_days']} дн.) & {db['raw_ticks_total']} $\\rightarrow$ {db['merged_rows_total']} ({db['row_compression_ratio']}$\\times$) \\\\",
            f"Размер SQLite БД со склейкой / без склейки & {db['merged_db_size_kb']} КБ / {db['estimated_raw_db_size_mb']} МБ \\\\",
            f"Агрегация топ-10 приложений за 1 / 30 дн. & {db['queries_ms']['top_apps_1_day']} / {db['queries_ms']['top_apps_30_days']} мс \\\\",
            f"Выборка таймлайна за 1 день & {db['queries_ms']['timeline_1_day']} мс \\\\",
        ]
    )

    body = "\n        ".join(rows)
    return (
        "\\begin{table}[htbp]\n"
        "    \\centering\n"
        "    \\caption{Результаты нагрузочного тестирования приложения}\n"
        "    \\label{tab:benchmark_results}\n"
        "    \\begin{tabular}{|l|r|}\n"
        "        \\hline\n"
        "        \\textbf{Метрика} & \\textbf{Значение} \\\\\n"
        "        \\hline\n"
        f"        {body}\n"
        "        \\hline\n"
        "    \\end{tabular}\n"
        "\\end{table}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Бенчмарк производительности Activity Tracker (для отчёта курсовой)."
    )
    parser.add_argument("--duration", type=int, default=30, help="Длительность замера адаптера (сек)")
    parser.add_argument("--interval", type=float, default=1.0, help="Интервал опроса (сек)")
    parser.add_argument("--days", type=int, default=30, help="Число симулируемых рабочих дней для БД")
    parser.add_argument("--pid", type=int, default=None, help="PID запущенного main.py для замера GUI CPU/RAM")
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "benchmarks" / "benchmark_report.json",
        help="Путь сохранения JSON-отчёта",
    )
    args = parser.parse_args()

    adapter_res = benchmark_platform_adapter(args.duration, args.interval)
    db_res = benchmark_database_and_heartbeat(args.days)

    report = {
        "environment": {
            "os": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        },
        "adapter_benchmark": adapter_res,
        "database_benchmark": db_res,
    }

    if args.pid:
        report["gui_benchmark"] = benchmark_running_gui(args.pid, min(args.duration, 30))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    tex_path = args.out.with_suffix(".tex")
    tex_path.write_text(generate_latex_table(report), encoding="utf-8")

    print("\n=== ИТОГИ БЕНЧМАРКА ===")
    print(f"ОС / Адаптер:   {report['environment']['os']} | {adapter_res['adapter_name']}")
    print(
        f"Активное окно:  avg={adapter_res['window_query_ms']['avg']} мс, "
        f"p95={adapter_res['window_query_ms']['p95']} мс"
    )
    print(
        f"Время простоя:  avg={adapter_res['idle_query_ms']['avg']} мс, "
        f"p95={adapter_res['idle_query_ms']['p95']} мс"
    )
    print(
        f"Фон CPU / RAM:  {adapter_res['headless_cpu_percent']['avg']}% / "
        f"{adapter_res['headless_ram_mb']['avg']} МБ"
    )
    if "gui_benchmark" in report:
        g = report["gui_benchmark"]
        print(f"GUI CPU / RAM:  {g['gui_cpu_percent']['avg']}% / {g['gui_ram_mb']['avg']} МБ")
    print(
        f"БД ({db_res['simulated_days']} дн.):   {db_res['raw_ticks_total']} -> "
        f"{db_res['merged_rows_total']} строк ({db_res['row_compression_ratio']}x), "
        f"размер {db_res['merged_db_size_kb']} КБ вместо ~{db_res['estimated_raw_db_size_mb']} МБ"
    )
    print(
        f"SQL (1д / 30д): {db_res['queries_ms']['top_apps_1_day']} мс / "
        f"{db_res['queries_ms']['top_apps_30_days']} мс"
    )
    print(f"\nСохранено: {args.out}")
    print(f"LaTeX:     {tex_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())