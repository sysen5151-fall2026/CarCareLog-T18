"""Regression checks for V03 study accounting. Fixtures here do not represent first-time owners."""

import base64
from contextlib import closing
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import receipt_owner_study as study


LABEL = {"service_date": "2025-01-15", "service_item": "Oil change", "category": "Maintenance",
         "mileage": 23000, "cost": "74.98", "provider": "Test Garage"}
ROW = {**LABEL, "id": 2, "vehicle_id": 1, "cost_cents": 7498, "service_items": ["Oil change"]}
CASE = {"id": "A", "label": LABEL}
OBS = {"saved_id": 2, "saved_at": 109.2, "saved_draft": {**LABEL, "cost": "70.00"}}


class OwnerStudyTests(unittest.TestCase):
    def test_complete_time_and_corrections(self):
        result = study.grade(OBS, 10.0, 190.0, [ROW], CASE, "ai", False)
        self.assertEqual(result["changed_draft_fields"], ["cost"])
        self.assertEqual(result["server_save_seconds"], 99.2)
        self.assertTrue(result["passed_180"])
        self.assertFalse(study.grade(OBS, 10, 190.01, [ROW], CASE, "ai", False)["passed_180"])

    def test_degraded_missing_help_wrong_and_duplicate_do_not_pass(self):
        attempts = [({}, [], False), ({**OBS, "saved_draft": None}, [ROW], False), (OBS, [ROW], True),
                    (OBS, [{**ROW, "provider": "Wrong shop"}], False), (OBS, [ROW, ROW], False),
                    (OBS, [{**ROW, "vehicle_id": 5}], False), ({**OBS, "edited_after_save": True}, [ROW], False),
                    (OBS, [{**ROW, "service_items": ["Oil change", "Brake service"]}], False)]
        for observation, rows, helped in attempts:
            with self.subTest(observation=observation, rows=rows, helped=helped):
                self.assertFalse(study.grade(observation, 10, 125, rows, CASE, "ai", helped)["passed_180"])

    def test_distinct_people_paired_time_and_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            good = study.grade(OBS, 0, 110, [ROW], CASE, "ai", False)
            manual = study.grade({}, 0, 150, [], CASE, "manual", False)
            for person in study.PARTICIPANTS[:9]:
                study.write_new(folder / f"{person}-ai.json", good)
            study.write_new(folder / "P01-manual.json", {**manual, "correct_save": True})
            study.write_new(folder / "P02-manual.json", manual)
            self.assertEqual(study.summarize(folder)["v03"], "pending")
            study.write_new(folder / "P10-ai.json", {**good, "passed_180": False})
            summary = study.summarize(folder)
            self.assertEqual((summary["passed_within_180s"], summary["v03"]), (9, "met"))
            self.assertEqual((summary["correct_unaided_pairs"], summary["paired_median_seconds_saved_with_ai"]), (1, 40))
            with self.assertRaises(FileExistsError):
                study.write_new(folder / "P01-ai.json", good)

    def test_benchmark_counts_unavailable_photo(self):
        png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aWQAAAAASUVORK5CYII=")
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            cases = [{**CASE, "id": name, "condition": "fixture", "image": name + ".png"} for name in ("A", "B")]
            for index, case in enumerate(cases):
                (folder / case["image"]).write_bytes(png + bytes([index]))
            (folder / "cases.json").write_text(json.dumps(cases), encoding="utf-8")
            cases = study.read_cases(folder)
            raw = {**LABEL, "odometer_value": 23000, "odometer_unit": "km"}
            with patch.object(study.receipt_runtime, "draft_receipt",
                              side_effect=[raw, study.receipt_runtime.ReceiptRuntimeUnavailable()]):
                report = study.benchmark(folder, cases)
            self.assertEqual((report["correct_fields"], report["attempted_fields"]), (6, 12))
            self.assertFalse(report["per_photo"][1]["draft_returned"])
            self.assertNotIn("Test Garage", json.dumps(report))

    def test_observer_sees_assigned_photo_and_confirmed_database_write(self):
        photo = b"\x89PNG\r\n\x1a\nfixture"
        observed = {}
        case = {**CASE, "digest": sha256(photo).digest()}
        handler = study.study_handler(case, observed)

        def request(path, body):
            connection = Mock()
            payload = json.dumps(body).encode()
            headers = (f"POST {path} HTTP/1.0\r\nHost: 127.0.0.1:8018\r\n"
                       f"Content-Type: application/json\r\nContent-Length: {len(payload)}\r\n\r\n")
            connection.makefile.return_value = BytesIO(headers.encode() + payload)
            sent = BytesIO()
            connection.sendall.side_effect = sent.write
            handler(connection, ("127.0.0.1", 30000), Mock(server_port=8018))
            return sent.getvalue()

        with tempfile.TemporaryDirectory() as directory, patch.object(study.app, "DB_PATH", Path(directory) / "receipt.db"):
            study.app.init_db()
            with closing(study.app.connect()) as db, db:
                db.execute("INSERT INTO vehicles(name,mileage) VALUES ('Study vehicle',0)")
            raw = {**LABEL, "cost": "70.00", "odometer_value": 23000, "odometer_unit": "km"}
            with patch.dict(study.os.environ, {"CARCARE_OLLAMA_MODEL": study.receipt_runtime.PINNED_MODEL}), \
                 patch.object(study.app, "draft_receipt", return_value=raw):
                for image, expected in [(photo + b"other", False), (photo, True)]:
                    response = request("/api/receipt-draft", {"vehicle_id": 1, "receipt_image": base64.b64encode(image).decode()})
                    self.assertIn(b"200 OK", response)
                    self.assertEqual(observed["draft"] is not None, expected)
            result = request("/api/records", {**LABEL, "vehicle_id": 1, "owner_confirmed": True})
            self.assertIn(b"201 Created", result)
            with closing(study.app.connect()) as db:
                rows = study.app.all_records(db, 1)
            start = observed["saved_at"] - 20
            graded = study.grade(observed, start, start + 25, rows, case, "ai", False)
            self.assertTrue(graded["passed_180"])
            self.assertEqual(graded["changed_draft_fields"], ["cost"])


if __name__ == "__main__":
    unittest.main()
