"""Requirement-linked checks for the implemented F.2.2 manual path.

These checks cover selected behaviors, not full ASR/FCS system acceptance.
"""
import unittest
from datetime import date
from unittest.mock import patch
import test_app
from backend import function_f22 as f22


class FunctionalRequirementTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown
    call = test_app.AppTests.call
    car = test_app.AppTests.car
    record = test_app.AppTests.record
    dashboard = test_app.AppTests.dashboard
    rule = test_app.AppTests.rule

    def test_ASR_1_4_1_route_existing_vehicle(self):
        car = self.car()
        self.assertEqual(self.record(car)[0], 201)
        self.assertEqual(self.record(999999)[0], 404)
        self.assertEqual(self.record(car, operation="unknown")[0], 400)
        self.assertEqual(len(self.dashboard(car)["records"]), 1)

    def test_ASR_1_2_1_reject_unconfirmed_transaction(self):
        car = self.car()
        for confirmation in (False, None, "true", 1):
            self.assertEqual(self.record(car, owner_confirmed=confirmation)[0], 400)
        self.assertEqual(self.dashboard(car)["records"], [])

    def test_ASR_1_4_3_commit_then_return_record_id(self):
        car = self.car()
        status, stored = self.record(car, cost="89.99")
        self.assertEqual(status, 201)
        data = self.dashboard(car)
        self.assertEqual(data["records"][0]["id"], stored["id"])
        self.assertEqual(data["total_cents"], 8999)
        original = data["records"][0]
        self.assertEqual(self.call(f'/api/records/{stored["id"]}', "PUT",
            {**original, "cost": "99.99"})[0], 400)
        self.assertEqual(self.dashboard(car)["total_cents"], 8999)

    def test_ASR_1_4_4_or_thresholds_and_confirmed_source(self):
        records = [dict(id=4, service_date="2026-10-31", service_item="Oil change",
            mileage=52000, category="Maintenance", cost_cents=8999)]
        rules = [dict(service_item="Oil change", interval_km=8000, interval_months=6)]
        data = f22.calculate_maintenance_summary_and_reminders(records, rules,
            vehicle_context={"id": 1, "mileage": 52000}, as_of=date(2026, 11, 1))
        reminder = data["reminders"][0]
        self.assertEqual((reminder["due_date"], reminder["due_mileage"], reminder["record_id"]),
                         ("2027-04-30", 60000, 4))
        for mileage, day in [(60000, date(2026, 11, 1)), (52000, date(2027, 4, 30))]:
            result = f22.calculate_maintenance_summary_and_reminders(records, rules,
                vehicle_context={"id": 1, "mileage": mileage}, as_of=day)
            self.assertEqual(result["reminders"][0]["status"], "Due / overdue")

    def test_FCS_2_1_2_manual_path_independent_of_external_AI(self):
        # A synthesis contribution only. This does not measure availability uptime.
        car = self.car()
        with patch.object(f22, "coordinate_ai_requests_and_responses",
                          side_effect=RuntimeError("AI unavailable")) as ai:
            self.assertEqual(self.record(car)[0], 201)
            self.assertEqual(len(self.dashboard(car)["records"]), 1)
            ai.assert_not_called()

    def test_ASR_1_4_2_external_AI_boundary_explicitly_unimplemented(self):
        # This verifies honest failure signaling, not successful AI extraction.
        with self.assertRaises(NotImplementedError):
            f22.coordinate_ai_requests_and_responses({},
                configured_ai_service_contract_limits={},
                authorized_records_and_source_references=[])


if __name__ == "__main__":
    unittest.main()
