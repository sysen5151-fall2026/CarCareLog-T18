import base64
import hashlib
import io
import sqlite3
import sys
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import manuals


class ManualTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE vehicles(id INTEGER PRIMARY KEY);
            INSERT INTO vehicles VALUES(1),(2);
            CREATE TABLE reminders(vehicle_id INTEGER, service_item TEXT, interval_km INTEGER,
                interval_months INTEGER, reference TEXT, UNIQUE(vehicle_id,service_item));
        """)
        manuals.init_schema(self.db)
        self.text = "Example only.\fOil change every 5,000 miles or 6 months."

    def store(self, **source):
        with self.db:
            return manuals.import_manual(self.db, 1, {"title": "Example manual", **source})

    def test_page_scoping_provenance_and_owner_confirmation(self):
        result = self.store(text=self.text)
        m = result["manual"]
        self.assertEqual(m["verification"], "owner_supplied")
        self.assertEqual(m["sha256"], hashlib.sha256(self.text.encode()).hexdigest())
        self.assertEqual(result["candidates"][0]["page"], 2)
        self.assertEqual(manuals.manual_evidence(self.db, 2), [])
        with self.assertRaises(LookupError):
            manuals.source_page(self.db, 2, m["id"], 1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM reminders").fetchone()[0], 0)
        confirm = {"manual_id": m["id"], "candidate_index": 0}
        with self.assertRaises(ValueError):
            manuals.confirm_interval(self.db, 1, confirm)
        with self.db:
            manuals.confirm_interval(self.db, 1, dict(confirm, owner_confirmed=True, interval_km=1))
        rule = self.db.execute("SELECT * FROM reminders").fetchone()
        self.assertEqual((rule["interval_km"], rule["interval_months"]), (8047, 6))
        self.assertIn(m["sha256"][:12], rule["reference"])
        self.assertIn("section 2", rule["reference"])

    def test_superseded_manual_and_failed_import(self):
        first = self.store(text=self.text)["manual"]
        self.assertEqual(self.store(text=self.text)["manual"]["id"], first["id"])
        with self.assertRaises(ValueError):
            self.store(file_base64="###")
        self.assertEqual(manuals.summary(self.db, 1)["manual"]["id"], first["id"])
        self.store(text="An owner's note without an interval.")
        with self.assertRaises(ValueError), self.db:
            manuals.confirm_interval(self.db, 1, {"manual_id": first["id"], "candidate_index": 0, "owner_confirmed": True})
        self.assertIn("5,000 miles", manuals.source_page(self.db, 1, first["id"], 2)["text"])
        self.assertNotIn("5,000 miles", manuals.manual_evidence(self.db, 1)[0]["text"])

    def test_interval_is_not_taken_from_another_maintenance_action(self):
        for sentence in ("Change oil every 6 months and inspect tire pressure every 1,000 miles.",
                         "Check tire pressure every 1,000 miles and replace engine oil as needed.",
                         "Check tire pressure every 1,000 miles, then change engine oil."):
            with self.subTest(sentence=sentence):
                self.assertEqual(manuals.extract_intervals([sentence]), [])
        single = manuals.extract_intervals(["Change oil every 5,000 miles or 6 months."])
        self.assertEqual((single[0]["interval_km"], single[0]["interval_months"]), (8047, 6))

    def test_publisher_and_metric_dual_units(self):
        url = "https://www.tesla.com/ownersmanual/model3/en_us/example.html"
        data = b"<head><title>Ignore</title></head><ul><li>Rotate tires every <b>6,250 miles\n (10,000 km)</b>\n or earlier if wear requires.</li></ul>"
        with patch.object(manuals, "download", return_value=(url, "text/html", data)):
            result = self.store(source_url=url)
        self.assertEqual(result["manual"]["verification"], "publisher_https")
        candidate = result["candidates"][0]
        self.assertEqual(candidate["interval_km"], 10_000)
        self.assertIn("if wear requires", candidate["quote"])
        self.assertNotIn("Ignore", manuals.manual_evidence(self.db, 1)[0]["text"])

    def test_no_milestones_ambiguous_ranges_or_unsupported_services(self):
        pages = ["Oil change at 15,000 km.\nOil change every 5,000–7,500 miles.\n"
                 "Oil change every 6 months or 12 months depending on conditions.\n"
                 "Change transmission fluid every 25,000 km.\nDo not rotate tires every 500 miles.\n"
                 "Oil change every 5,000 mi (30,000 km).\nOil change every 12 years."]
        self.assertEqual(manuals.extract_intervals(pages), [])

    def test_permitted_manufacturer_paths_only(self):
        self.assertEqual(manuals.publisher_url("https://techinfo.honda.com/rjanisis/pubs/x.pdf"),
                         "https://techinfo.honda.com/rjanisis/pubs/x.pdf")
        for url in ("http://www.tesla.com/ownersmanual/x", "https://localhost/x",
                    "https://www.tesla.com.example.org/ownersmanual/x",
                    "https://www.tesla.com/ownersmanual/../a", "https://www.tesla.com:8000/ownersmanual/x",
                    "https://www.tesla.com/ownersmanual/%2e%2e/a", "https://u@www.tesla.com/ownersmanual/a"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                manuals.publisher_url(url)

    def test_readable_pdf_upload(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
        except ImportError:
            self.skipTest("Install the optional PDF reader to run this check.")
        writer = PdfWriter()
        writer.add_blank_page(width=400, height=200)
        page = writer.add_blank_page(width=400, height=200)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 10 100 Td (Rotate tires every 8,000 km.) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        with closing(io.BytesIO()) as buf:
            writer.write(buf)
            result = self.store(file_base64=base64.b64encode(buf.getvalue()).decode())
        self.assertEqual([(r["page"], r["interval_km"]) for r in result["candidates"]], [(2, 8000)])
