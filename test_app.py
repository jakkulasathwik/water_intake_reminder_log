import os
import tempfile
import unittest
from models import WaterEntry
from datetime import datetime, timedelta
from storage import load_entries, save_entries, bulk_import_csv, next_entry_id
from analytics import build_daily_summaries, calculate_streak


class TestWaterIntakeReminderLog(unittest.TestCase):
    def test_daily_summary_and_thresholds(self):
        entries = [
            WaterEntry("WTR-1", "2026-11-20", "09:00", 1500, "Plain Water"),
            WaterEntry("WTR-2", "2026-11-20", "14:00", 1200, "Electrolyte / Sports"),
            WaterEntry("WTR-3", "2026-11-21", "10:00", 500, "Plain Water"),
        ]
        summaries = build_daily_summaries(entries, target_ml=2500)
        self.assertEqual(len(summaries), 2)
        self.assertEqual(summaries[0].status, "Target Met")
        self.assertIn("Dehydration Risk", summaries[1].status)

    def test_corrupted_json_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            jpath = os.path.join(tmp, "bad.json")
            cpath = os.path.join(tmp, "out.csv")
            with open(jpath, "w", encoding="utf-8") as f:
                f.write("{corrupted_json!!")
            recovered = load_entries(json_path=jpath, csv_path=cpath)
            self.assertEqual(len(recovered), 42)

    def test_bulk_csv_import_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            sample_csv = os.path.join(tmp, "import.csv")
            jpath = os.path.join(tmp, "logs.json")
            cpath = os.path.join(tmp, "logs.csv")
            with open(sample_csv, "w", encoding="utf-8") as f:
                f.write("date,time,amount_ml,category,note\n")
                f.write("2026-11-23,08:30,300,Plain Water,Valid\n")
                f.write("bad-date,08:30,300,Plain Water,Invalid date\n")
                f.write("2026-11-23,08:30,99999,Plain Water,Out of bounds\n")
            entries = []
            ok, errs = bulk_import_csv(sample_csv, entries, json_path=jpath, csv_path=cpath)
            self.assertEqual(ok, 1)
            self.assertEqual(len(errs), 2)

    def test_next_entry_id_is_unique_after_deletion(self):
        entries = [WaterEntry("WTR-1001", "2026-11-20", "09:00", 250, "Plain Water"),
                   WaterEntry("WTR-1003", "2026-11-20", "10:00", 250, "Plain Water")]
        self.assertEqual(next_entry_id(entries), "WTR-1004")
        self.assertEqual(next_entry_id([]), "WTR-1001")

    def test_goal_streak(self):
        today = datetime.now()
        entries = [WaterEntry(f"WTR-{i}", (today - timedelta(days=i)).strftime("%Y-%m-%d"), "09:00", 2600, "Plain Water")
                   for i in (1, 2, 3)]
        entries.append(WaterEntry("WTR-9", (today - timedelta(days=5)).strftime("%Y-%m-%d"), "09:00", 2600, "Plain Water"))
        self.assertEqual(calculate_streak(build_daily_summaries(entries, 2500)), 3)


if __name__ == "__main__":
    unittest.main()
