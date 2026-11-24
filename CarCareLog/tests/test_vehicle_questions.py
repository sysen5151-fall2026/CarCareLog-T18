"""Vehicle questions must cite persisted facts and avoid incorrectly broad totals."""

import unittest
from datetime import date
from unittest.mock import patch

from backend import knowledge
import test_app


def record(record_id, day, service, price, *, shop="Local Auto", others=()):
    return {"id": record_id, "service_date": day, "service_item": service,
            "service_items": [service, *others], "cost_cents": price, "provider": shop,
            "category": "Repair" if service in ("Brake service", "Battery") else "Maintenance",
            "mileage": 20000 + record_id, "notes": "Customer confirmed receipt."}


class VehicleQuestionTests(unittest.TestCase):
    def setUp(self):
        self.rows = [record(7, "2026-11-02", "Oil change", 15500, others=["Brake service"]),
                     record(3, "2026-10-01", "Brake service", 8499),
                     record(2, "2026-10-01", "Battery", 13799, shop="Town Garage"),
                     record(1, "2025-12-31", "Oil change", 5000)]
        self.pages = [{"id": 9, "title": "Example maintenance and care", "page": page, "text": content,
                       "verification": "owner_supplied", "source_url": ""}
                      for page, content in [(1, "Test vehicle information."), (4, "Check tire pressure cold. "
                                                         "Inflate demonstration tires to 32 psi when cold.")]]

    def ask(self, question, **opts):
        return knowledge.answer_question(question, self.rows, self.pages, today=date(2026, 11, 15), **opts)

    def test_mileage_and_dollar_questions_use_the_requested_measure(self):
        self.rows[1]["mileage"] = 90000
        result = self.ask("What was the highest recorded mileage?")
        self.assertEqual(result["record_ids"], [3])
        self.assertIn("90,000 km", result["answer"])
        self.assertIn("recorded mileage", result["answer"])
        result = self.ask("How many dollars did I spend?")
        self.assertIn("$427.98", result["answer"])
        self.assertEqual(self.ask("How many invoices?")["method"], "Confirmed record count")
        self.assertNotIn("spending", self.ask("What is my total mileage?")["answer"].lower())

    def test_provider_and_date_filter_exact_cents_and_periods(self):
        answer = self.ask("How much did I spend at Local Auto in October 2026?")
        self.assertEqual(answer["record_ids"], [3])
        self.assertIn("$84.99", answer["answer"])
        self.assertEqual(self.ask("How many records last month?")["record_ids"], [3, 2])
        self.assertEqual(self.ask("How much did I pay last year?")["record_ids"], [1])
        self.assertEqual(self.ask("List records from 2026-10-01 through 2026-11-02")["record_ids"], [7, 3, 2])
        self.assertEqual(self.ask("How much did I spend on repairs this year?")["record_ids"], [3, 2])
        self.assertEqual(self.ask("Which repair had the highest invoice?")["record_ids"], [2])
        self.assertEqual(self.ask("When was my earliest oil change?")["record_ids"], [1])

    def test_no_missing_line_item_prices_or_unsupported_aggregate(self):
        answer = self.ask("How much did I spend on brakes in 2026?")
        self.assertEqual(answer["record_ids"], [7, 3])
        self.assertIn("$84.99", answer["answer"])
        self.assertIn("unknown", answer["answer"])
        for question in ("How much did I spend at Unknown Garage?", "How much did I spend under $100?",
                         "How much did I spend before 2026?", "How much did I spend on air conditioning?",
                         "How much did I spend excluding repairs?", "How much did I spend in October?",
                         "What was the average battery cost?"):
            with self.subTest(question=question):
                self.assertNotEqual(self.ask(question)["method"], "Confirmed invoice amounts")
        self.assertEqual(self.ask("How much did I spend in 2030?")["record_ids"], [])

    def test_exact_manual_quote_with_page_and_no_cross_source(self):
        answer = self.ask("What tire pressure does the manual recommend?")
        self.assertEqual(answer["record_ids"], [])
        self.assertTrue(answer["manual_sources"])
        for source in answer["manual_sources"]:
            self.assertEqual((source["id"], source["page"]), (9, 4))
            self.assertIn(source["quote"], self.pages[1]["text"])
            self.assertEqual(source["verification"], "owner_supplied")
        self.assertEqual(self.ask("What tire pressure does the manual recommend?", source="history")["manual_sources"], [])
        self.assertEqual(self.ask("How much did I spend on brakes?", source="manual")["record_ids"], [])
        answer = knowledge.answer_question("What does the manual say about brakes?", self.rows, [],
                                           today=date(2026, 11, 15))
        self.assertEqual(answer["manual_sources"], [])
        self.assertIn("No imported manual", answer["answer"])

    def test_loopback_rephrasing_can_only_return_source_text(self):
        with patch.object(knowledge.receipt_runtime, "_call_runtime", return_value={
                "response": '{"terms":["pressure","tire"]}'}) as request:
            result = self.ask("pneumatic specification?", source="manual", model="qwen3.5:4b")
        self.assertEqual(result["manual_sources"][0]["page"], 4)
        self.assertIn(result["manual_sources"][0]["quote"], self.pages[1]["text"])
        self.assertNotIn("Test vehicle", request.call_args.args[2]["prompt"])
        with patch.object(knowledge.receipt_runtime, "_call_runtime", side_effect=OSError):
            self.assertEqual(self.ask("zebra quasar?", model="qwen3.5:4b")["method"], "Insufficient evidence")
        with patch.object(knowledge.receipt_runtime, "_call_runtime", return_value={"response": "made up"}):
            self.assertEqual(self.ask("zebra quasar?", model="qwen3.5:4b")["record_ids"], [])

    def test_input_bounds_and_vehicle_with_no_records(self):
        for value in (None, "", " ", "?" * 601):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.ask(value)
        with self.assertRaises(ValueError):
            self.ask("Some question", source="all owners")
        with self.assertRaises(ValueError):
            self.ask("How much from 2026-10-01 through 2025-01-01?")
        answer = knowledge.answer_question("What is my total spending?", [], [], today=date.today())
        self.assertEqual(answer["method"], "Insufficient evidence")


class VehicleQuestionsHTTPTests(unittest.TestCase):
    setUp = test_app.AppTests.setUp
    tearDown = test_app.AppTests.tearDown
    call = test_app.AppTests.call
    car = test_app.AppTests.car
    record = test_app.AppTests.record

    def test_record_and_manual_sources_follow_selected_vehicle(self):
        one, two = self.car("One"), self.car("Two")
        status, first = self.record(one, service_item="Inspection", cost="90.50")
        self.assertEqual(status, 201)
        self.record(two, service_item="Inspection", cost="800.00")
        for car, number in [(one, "32"), (two, "44")]:
            status, _ = self.call("/api/manual/import", "POST", {
                "vehicle_id": car, "title": "Vehicle test manual", "text": f"Cold tire pressure: {number} psi."})
            self.assertEqual(status, 200)
        status, result = self.call("/api/questions", "POST", {"vehicle_id": one, "question": "What was my total spending?"})
        self.assertEqual(status, 200)
        self.assertEqual(result["record_ids"], [first["id"]])
        self.assertIn("$90.50", result["answer"])
        status, result = self.call("/api/questions", "POST", {
            "vehicle_id": one, "question": "What tire pressure does my manual recommend?"})
        self.assertEqual(status, 200)
        self.assertEqual(len(result["manual_sources"]), 1)
        citation = result["manual_sources"][0]
        self.assertEqual(citation["quote"], "Cold tire pressure: 32 psi.")
        path = f"/api/manual/page?manual_id={citation['id']}&page={citation['page']}&vehicle_id="
        self.assertEqual(self.call(path + str(one))[1]["text"], citation["quote"])
        self.assertNotEqual(self.call(path + str(two))[0], 200)
