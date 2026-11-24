"""Test the V07 collector's clock accounting and its operating-product read."""
from contextlib import closing
import sqlite3
import tempfile
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import availability_study as study


class AvailabilityStudyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.config = study.configure(self.db, 8000, 1)
        self.start = self.config[0]

    def sample(self, slot, result="ok"):
        now = self.start + slot * 60 + 1
        study.observe(self.db, self.config, now, clock=lambda: now, read=lambda *args: result)

    def test_skipped_minutes_and_deduplication(self):
        self.sample(0)
        self.sample(0, "unreachable")
        self.sample(3, "http-500")
        summary = study.report(self.db, self.start + 240)
        self.assertEqual((summary["observed_ok"], summary["observed_failed"],
                          summary["missing_or_interrupted"], summary["v07"]), (1, 1, 2, "pending"))

    def test_exact_clock_and_threshold(self):
        self.db.executemany("INSERT INTO v07_samples VALUES(?,?,?,0)",
                            ((n, self.start+n*60, "ok") for n in range(9979)))
        finish = self.start + 604800
        self.assertEqual(study.report(self.db, finish-1)["v07"], "pending")
        self.assertEqual(study.report(self.db, finish)["v07"], "fail")
        self.sample(9979)
        self.assertEqual(study.report(self.db, finish)["v07"], "pass")
        self.assertEqual(study.report(self.db, finish)["missing_or_interrupted"], 100)

    def test_interrupted_and_late_reads_never_count_as_available(self):
        def interrupted(*args):
            raise KeyboardInterrupt

        with self.assertRaises(KeyboardInterrupt):
            study.observe(self.db, self.config, self.start+1, clock=lambda: self.start+1,
                          read=interrupted)
        self.sample(0)
        ticks = iter([self.start+61, self.start+120])
        study.observe(self.db, self.config, self.start+61, clock=lambda: next(ticks), read=lambda *args: "ok")
        self.assertEqual(study.report(self.db, self.start+120)["observed_ok"], 0)
        self.assertEqual(study.report(self.db, self.start+120)["missing_or_interrupted"], 1)

    def test_resume_keeps_same_window_and_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "v07.sqlite3"
            with closing(sqlite3.connect(path)) as first:
                config = study.configure(first, 8002, 2)
                now = config[0] + 10
                study.observe(first, config, now, clock=lambda: now, read=lambda *args: "ok")
            with closing(sqlite3.connect(path)) as reopened:
                self.assertEqual(study.configure(reopened, None, None), config)
                self.assertEqual(study.report(reopened, now+60)["observed_ok"], 1)
                with self.assertRaises(ValueError):
                    study.configure(reopened, 8003, None)


if __name__ == "__main__":
    unittest.main()
