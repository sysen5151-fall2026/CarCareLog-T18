import csv
import hashlib
import io
import json
import unittest
from contextlib import closing
from unittest.mock import patch

import test_app
from backend import function_f22, receipt_runtime


class MultiServiceTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown
    call = test_app.AppTests.call
    car = test_app.AppTests.car
    record = test_app.AppTests.record
    dashboard = test_app.AppTests.dashboard
    rule = test_app.AppTests.rule

    def test_one_invoice_one_total_two_reminders_and_stable_retry(self):
        car = self.car()
        services = ["Tire rotation", "Oil change"]
        for service in services:
            self.rule(car, service=service)
        fields = dict(service_item=services[0], service_items=services, cost="180.00",
                      operation_id="same-invoice-from-browser")
        status, saved = self.record(car, **fields)
        self.assertEqual(status, 201)
        self.assertEqual(self.record(car, **fields), (201, saved))
        self.assertEqual(self.record(car, **{**fields, "service_items": [services[0]]})[0], 409)
        data = self.dashboard(car)
        self.assertEqual((len(data["records"]), data["total_cents"]), (1, 18000))
        self.assertEqual(data["monthly"][0]["Maintenance"], 18000)
        self.assertEqual(data["records"][0]["service_items"], services)
        self.assertEqual([r["record_id"] for r in data["reminders"]], [saved["id"]] * 2)
        _, output = self.call(f"/api/export?vehicle_id={car}")
        rows = list(csv.DictReader(io.StringIO(output.decode("utf-8-sig"))))
        self.assertEqual([(row["Service"], row["Cost (USD)"]) for row in rows],
                         [("Tire rotation + Oil change", "180.00")])
        _, answer = self.call(f"/api/answer?vehicle_id={car}&question=oil")
        self.assertEqual(answer["record_ids"], [saved["id"]])

    def test_legacy_client_edits_validation_and_replace_service_list(self):
        car = self.car()
        _, saved = self.record(car, service_items=["Oil change", "Tire rotation", "Inspection"])
        path = f"/api/records/{saved['id']}"
        fields = dict(self.dashboard(car)["records"][0], owner_confirmed=True, cost="80.25")
        fields.pop("service_items")
        self.assertEqual(self.call(path, "PUT", {**fields, "service_item": "Inspection"})[0], 200)
        self.assertEqual(self.dashboard(car)["records"][0]["service_items"], ["Inspection", "Tire rotation"])
        for invalid in ([], ["Brake service"], ["Oil change", "Oil change"], ["Oil change", {}], None):
            self.assertEqual(self.call(path, "PUT", {**fields, "service_items": invalid})[0], 400)
        self.assertEqual(self.dashboard(car)["records"][0]["service_items"], ["Inspection", "Tire rotation"])
        self.assertEqual(self.call(path, "PUT", {**fields, "service_items": ["Oil change"]})[0], 200)
        self.assertEqual(self.dashboard(car)["records"][0]["service_items"], ["Oil change"])
        self.assertEqual(self.call(path, "DELETE")[0], 200)
        self.assertEqual(self.dashboard(car)["records"], [])

    def test_preupgrade_single_service_data_and_operation_fingerprint(self):
        car = self.car()
        key = "previous-release-save-id"
        day = "2026-01-02"
        old_fields = [day, "Oil change", "Maintenance", 10000, 8025, "Garage", ""]
        fingerprint = hashlib.sha256(json.dumps(old_fields, ensure_ascii=False,
            separators=(",", ":")).encode("utf-8")).hexdigest()
        with closing(test_app.app.connect()) as db, db:
            db.execute("DROP TABLE record_additional_services")  # Original pilot schema.
            old_id = db.execute("INSERT INTO records(vehicle_id,service_date,service_item,category,"
                "mileage,cost_cents,provider,notes) VALUES(?,?,?,?,?,?,?,?)", (car, *old_fields)).lastrowid
            db.execute("INSERT INTO record_operations(vehicle_id,operation_id,fingerprint,record_id) "
                       "VALUES(?,?,?,?)", (car, key, fingerprint, old_id))
        test_app.app.init_db()
        self.assertEqual(self.record(car, service_date=day, operation_id=key), (201, {"id": old_id}))
        data = self.dashboard(car)
        self.assertEqual((len(data["records"]), data["total_cents"]), (1, 8025))
        self.assertEqual(data["records"][0]["service_items"], ["Oil change"])


class MultiServiceDraftTests(unittest.TestCase):
    def test_pinned_runtime_suggests_only_reviewable_supported_services(self):
        request = receipt_runtime.build_request("Oil change and tire rotation", receipt_runtime.PINNED_MODEL)
        self.assertIn("service_items", request["format"]["required"])
        proposal = dict.fromkeys(receipt_runtime.DRAFT_FIELDS)
        proposal.update(service_item="Oil change", service_items=["Tire rotation", "Fake", "Oil change"])
        result = function_f22.review_receipt_draft(proposal, None)
        self.assertEqual(result["service_items"], ["Oil change", "Tire rotation"])
        self.assertEqual(result["evidence"]["service_item"]["status"], "check")
        with patch.object(receipt_runtime, "_call_runtime", return_value={"response": "{}"}):
            with self.assertRaises(receipt_runtime.ReceiptRuntimeUnavailable):
                receipt_runtime.draft_receipt("Receipt", receipt_runtime.PINNED_MODEL)
