"""Owner-reviewed duplicate saves and vehicle-scoped history lookups."""

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import test_app


class ReceiptHistoryTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown
    call = test_app.AppTests.call
    car = test_app.AppTests.car
    record = test_app.AppTests.record
    dashboard = test_app.AppTests.dashboard

    def test_duplicate_race_and_explicit_separate_save(self):
        car = self.car()
        def save(key, reviewed=None):
            return self.record(car, check_duplicates=True, acknowledged_duplicate_ids=reviewed or [],
                               operation_id=key)
        keys = ["independent-action-001", "independent-action-002"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, keys))
        self.assertEqual(sorted(status for status, _ in results), [201, 409])
        winner = next(body["id"] for status, body in results if status == 201)
        loser_key = keys[next(i for i, (status, _) in enumerate(results) if status == 409)]
        warning = next(body for status, body in results if status == 409)
        self.assertEqual(warning["code"], "possible_duplicate")
        self.assertEqual([r["id"] for r in warning["matches"]], [winner])
        self.assertEqual(warning["matches"][0]["cost_cents"], 8025)
        self.assertEqual(len(self.dashboard(car)["records"]), 1)
        status, second = save(loser_key, [winner])
        self.assertEqual(status, 201)
        self.assertNotEqual(second["id"], winner)
        self.assertEqual(save(loser_key), (201, second))
        status, fresh_warning = save("independent-action-003", [winner])
        self.assertEqual(status, 409)
        self.assertEqual({r["id"] for r in fresh_warning["matches"]}, {winner, second["id"]})
        self.assertEqual(len(self.dashboard(car)["records"]), 2)

    def test_duplicate_boundaries_and_shop_normalization(self):
        car, other = self.car(), self.car("Second car")
        def save(vehicle_id, shop, **changes):
            return self.record(vehicle_id, provider=shop, check_duplicates=True, **changes)
        _, original = save(car, "  Local Auto  ")
        status, warning = save(car, "lOcal   AUTO")
        self.assertEqual(status, 409)
        self.assertEqual([r["id"] for r in warning["matches"]], [original["id"]])
        for vehicle_id, shop, changes in [(other, "Local Auto", {}), (car, "Another Auto", {}),
                                          (car, "Local Auto", {"cost": "80.24"}),
                                          (car, "Local Auto", {"service_date": "2020-01-07"}),
                                          (car, "", {}), (car, "", {})]:
            self.assertEqual(save(vehicle_id, shop, **changes)[0], 201)
        self.assertEqual(save(car, "Local Auto", acknowledged_duplicate_ids=[True])[0], 400)
        self.assertEqual(save(car, "Local Auto", owner_confirmed=False,
                              acknowledged_duplicate_ids=[original["id"]])[0], 400)

    def test_history_disambiguates_mixed_bills_and_lists_only_matching_sources(self):
        car, other = self.car(), self.car("Second car")
        year = date.today().year
        this_year = f"{year}-01-01"
        def answer(kind, suffix=""):
            status, result = self.call(f"/api/answer?vehicle_id={car}&question={kind}{suffix}")
            self.assertEqual(status, 200)
            return result
        self.assertEqual(answer("tire_rotation")["record_ids"], [])
        self.assertEqual(answer("brake_spending")["record_ids"], [])
        _, old = self.record(car, service_date=f"{year-1}-12-31", service_item="Brake service", cost="25.50")
        _, brake = self.record(car, service_date=this_year, service_item="Brake service", cost="99.99")
        self.record(other, service_date=this_year, service_item="Brake service", cost="500.00")
        just_brakes = answer("brake_spending")
        self.assertIn("$99.99", just_brakes["answer"])
        self.assertEqual(just_brakes["record_ids"], [brake["id"]])
        _, bundle = self.record(car, service_date=this_year, service_item="Oil change",
            service_items=["Oil change", "Tire rotation", "Brake service"], mileage=12345, cost="180.00")
        partial = answer("brake_spending")
        self.assertIn("$99.99", partial["answer"])
        self.assertIn("exact brake total is unknown", partial["answer"])
        self.assertNotIn("279.99", partial["answer"])
        self.assertEqual(set(partial["record_ids"]), {brake["id"], bundle["id"]})
        last_year = answer("brake_spending", f"&year={year-1}")
        self.assertIn("$25.50", last_year["answer"])
        self.assertEqual(last_year["record_ids"], [old["id"]])
        rotation = answer("tire_rotation")
        self.assertIn("12,345 km", rotation["answer"])
        self.assertIn(this_year, rotation["answer"])
        self.assertEqual(rotation["record_ids"], [bundle["id"]])
        self.assertEqual(self.call(f"/api/answer?vehicle_id={car}&question=brake_spending&year=no")[0], 400)
