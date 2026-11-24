import re
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from backend import app
from backend.calendar_export import reminder_event


class CalendarExportTest(unittest.TestCase):
    day = date(2026, 11, 23)

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "legacy.db"
        app.init_db(path)
        self.db = app.connect(path)
        self.addCleanup(self.db.close)
        vehicle_id = app.seed_demo(self.db)
        data = app.dashboard(self.db, vehicle_id)
        self.car = data["vehicle"]
        self.rule = dict(data["reminders"][0], status="Upcoming", due_date="2026-12-10")

    def event(self, **kwargs):
        return reminder_event(self.db, self.car, {**self.rule, **kwargs}, today=self.day)

    def test_future_event_and_stable_occurrence(self):
        first = self.event()
        second = self.event()
        uid = re.compile(rb"UID:[^\r]+")
        self.assertEqual(uid.search(first)[0], uid.search(second)[0])
        self.assertNotEqual(uid.search(first)[0], uid.search(self.event(due_date="2027-01-10"))[0])
        self.assertRegex(first, rb"DTSTAMP:\d{8}T\d{6}Z\r\n")
        self.assertIn(b"DTSTART:20261210T090000\r\n", first)
        self.assertIn(b"BEGIN:VALARM\r\nTRIGGER:-P1D\r\nACTION:DISPLAY\r\n", first)
        self.assertNotIn(b"\n", first.replace(b"\r\n", b""))
        self.assertTrue(first.endswith(b"END:VCALENDAR\r\n"))

    def test_near_term_and_unexportable_rules(self):
        tomorrow = (self.day + timedelta(days=1)).isoformat()
        self.assertIn(b"TRIGGER:PT0S\r\n", self.event(due_date=tomorrow))
        for fields in ({"due_date": None}, {"due_date": "2026-11-23"}, {"due_date": "2026-11-22"},
                       {"due_date": "bad date"}, {"status": "Due / overdue"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.event(**fields)

    def test_unicode_text_fold_and_escaping(self):
        self.car["name"] = "车辆" * 35 + "\\fleet, A;B\r\nATTENDEE:sample"
        result = self.event()
        self.assertTrue(all(len(line) <= 75 for line in result.split(b"\r\n")))
        for line in result.split(b"\r\n"):
            line.decode("utf-8")
        unfolded = result.replace(b"\r\n ", b"").decode("utf-8")
        self.assertIn("车辆" * 35 + r"\\fleet\, A\;B\nATTENDEE:sample", unfolded)
        self.assertNotIn("\r\nATTENDEE:", unfolded)
