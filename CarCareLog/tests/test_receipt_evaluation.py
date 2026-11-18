"""Checks for the labeled receipt samples and the Lab 13 evaluation scoring."""

from datetime import date
import itertools
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import evaluate_receipts as ev  # noqa: E402
from backend import receipt_runtime  # noqa: E402

TODAY = date(2026, 11, 18)


class ReceiptEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = ev.load_samples()

    def run_with(self, drafter):
        clock = itertools.count(0, 0.5)
        results = ev.evaluate(self.samples, drafter, today=TODAY, clock=lambda: next(clock))
        return results, ev.summarize(results)

    def test_samples_are_labeled_and_cover_the_hard_cases(self):
        self.assertGreaterEqual(len(self.samples), 20)
        self.assertEqual(len({s["id"] for s in self.samples}), len(self.samples))
        for sample in self.samples:
            self.assertEqual(set(sample["label"]), set(ev.FIELDS))
            self.assertEqual(set(sample["ideal_draft"]), set(receipt_runtime.DRAFT_FIELDS))
        units = {s["ideal_draft"]["odometer_unit"] for s in self.samples}
        self.assertEqual(units, {"km", "mi", None})
        self.assertTrue(any("ignore your instructions" in s["text"] for s in self.samples))
        self.assertTrue(any(s["label"]["service_date"] is None for s in self.samples))
        self.assertTrue(any(s["label"]["provider"] is None for s in self.samples))

    def test_a_perfect_model_scores_every_value_correct(self):
        by_text = {s["text"]: s["ideal_draft"] for s in self.samples}
        results, summary = self.run_with(lambda text: dict(by_text[text]))
        self.assertEqual(summary["field_accuracy"], 1.0)
        self.assertEqual(summary["wrong_values"], 0)
        self.assertEqual(summary["receipts_all_fields_correct"], len(self.samples))
        # A perfect draft is still shown as found on the page, except fields that need the owner.
        statuses = {f: {r["fields"][f]["status"] for r in results} for f in ev.FIELDS}
        self.assertEqual(statuses["category"], {"check"})
        self.assertEqual(statuses["cost"], {"found"})
        self.assertEqual(summary["latency_seconds"]["first_request"], 0.5)

    def test_wrong_values_are_counted_as_flagged_or_unflagged(self):
        by_text = {s["text"]: s["ideal_draft"] for s in self.samples}

        def careless(text):
            draft = dict(by_text[text])
            draft["cost"] = "0.00"                   # not printed: flagged
            if draft["odometer_unit"] == "mi":
                draft["odometer_unit"] = "km"        # printed number, wrong unit: not flagged
            return draft

        results, summary = self.run_with(careless)
        cost = summary["per_field"]["cost"]
        zero_totals = sum(s["label"]["cost"] == "0.00" for s in self.samples)
        self.assertEqual((cost["correct"], cost["wrong_flagged"]), (zero_totals, len(self.samples) - zero_totals))
        miles = sum(s["ideal_draft"]["odometer_unit"] == "mi" for s in self.samples)
        self.assertEqual(summary["per_field"]["mileage"]["wrong_unflagged"], miles)
        self.assertEqual(summary["wrong_values_unflagged"], miles)

    def test_runtime_failures_are_reported_not_scored(self):
        def down(_text):
            raise receipt_runtime.ReceiptRuntimeUnavailable("down")

        results, summary = self.run_with(down)
        self.assertEqual(summary["runtime_failures"], len(self.samples))
        self.assertEqual(summary["field_values"], 0)
        self.assertIsNone(summary["field_accuracy"])

    def test_report_files_are_written(self):
        by_text = {s["text"]: s["ideal_draft"] for s in self.samples}
        results, summary = self.run_with(lambda text: dict(by_text[text]))
        run = {"model": receipt_runtime.PINNED_MODEL, "cold_start": True, "finished_utc": "2026-11-18T00:00:00+00:00",
               "machine": "test", "python": "3", "runtime": {"quantization_level": "Q4_K_M",
                                                             "weights_digest_matches_pin": True}}
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "eval"
            ev.write_report(summary, results, run, out)
            text = out.with_suffix(".md").read_text(encoding="utf-8")
            self.assertIn("Q4_K_M", text)
            self.assertIn("Wrong values shown as found", text)
            self.assertTrue(out.with_suffix(".json").exists())


if __name__ == "__main__":
    unittest.main()
