import tempfile
import unittest
from pathlib import Path

from core import ActivityCategorizer, ActivityDatabase


class TestCoreModule(unittest.TestCase):
    def setUp(self) -> None:
        self.db = ActivityDatabase(":memory:")
        self.categorizer = ActivityCategorizer(self.db.get_rules())

    def tearDown(self) -> None:
        self.db.close()

    def test_priority_categorization_inside_browser(self) -> None:
        cat_dev = self.categorizer.classify("chrome.exe", "GitHub - PySide6 Docs")
        cat_fun = self.categorizer.classify("chrome.exe", "YouTube - Music Mix")
        cat_web = self.categorizer.classify("chrome.exe", "Погода на завтра")

        names = {c.id: c.name for c in self.db.get_categories()}
        self.assertEqual(names[cat_dev], "Разработка")
        self.assertEqual(names[cat_fun], "Развлечения")
        self.assertEqual(names[cat_web], "Веб-сёрфинг")

    def test_heartbeat_merging_and_sleep_gap(self) -> None:
        cat_dev = self.categorizer.classify("code.exe", "main.py - VS Code")
        t0 = 1_700_000_000.0

        id1 = self.db.record_heartbeat("code.exe", "main.py - VS Code", t0 + 1, 1.0, False, cat_dev)
        id2 = self.db.record_heartbeat("code.exe", "main.py - VS Code", t0 + 2, 1.0, False, cat_dev)
        id3 = self.db.record_heartbeat("code.exe", "main.py - VS Code", t0 + 3, 1.0, False, cat_dev)
        self.assertEqual(id1, id2)
        self.assertEqual(id2, id3)

        id4 = self.db.record_heartbeat("code.exe", "main.py - VS Code", t0 + 63, 1.0, False, cat_dev)
        self.assertNotEqual(id3, id4)

        stats = self.db.get_period_stats(t0, t0 + 100)
        self.assertAlmostEqual(stats.active_seconds, 4.0, places=1)
        self.assertAlmostEqual(stats.productivity_index, 100.0, places=1)

    def test_export_csv_and_json(self) -> None:
        t0 = 1_700_000_000.0
        cat_dev = self.categorizer.classify("pycharm64.exe", "database.py")
        self.db.record_heartbeat("pycharm64.exe", "database.py", t0 + 5, 5.0, False, cat_dev)

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "report.csv"
            json_path = Path(tmp) / "report.json"
            self.assertEqual(self.db.export_csv(csv_path, t0, t0 + 10), 1)
            self.assertEqual(self.db.export_json(json_path, t0, t0 + 10), 1)
            self.assertTrue(csv_path.exists() and csv_path.stat().st_size > 0)
            self.assertTrue(json_path.exists() and json_path.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()