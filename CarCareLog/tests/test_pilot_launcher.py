"""Exercise the new-PC pilot safeguards with synthetic storage and no live cohort."""
from contextlib import closing
import json
from pathlib import Path
import socket
import sqlite3
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import run_availability_pilot as pilot


class PilotLauncherTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        with closing(socket.socket()) as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]

    def test_rejects_occupied_port_or_existing_data_before_creating_fixture(self):
        with closing(socket.socket()) as occupied:
            occupied.bind(("127.0.0.1", self.port))
            occupied.listen()
            with self.assertRaisesRegex(ValueError, "port"):
                pilot.identity(self.folder, self.port)
        self.assertEqual(list(self.folder.iterdir()), [])
        (self.folder / "owner-notes").write_text("retain", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "dedicated"):
            pilot.identity(self.folder, self.port)
        self.assertFalse((self.folder / "fixture").exists())

    def test_same_fixture_and_build_required_for_resume(self):
        saved = pilot.identity(self.folder, self.port)
        self.assertEqual(saved, pilot.identity(self.folder, None))
        self.assertFalse((self.folder / pilot.EVIDENCE).exists())
        with patch.object(pilot, "fingerprint", return_value="different"):
            with self.assertRaisesRegex(ValueError, "same extracted release"):
                pilot.identity(self.folder, None)

    def test_export_counts_match_raw_rows_and_existing_export_is_preserved(self):
        pilot.identity(self.folder, self.port)
        with closing(sqlite3.connect(self.folder / pilot.EVIDENCE)) as db, db:
            pilot.study.configure(db, self.port, 1)
            db.execute("UPDATE v07_pilot SET start=?", (time.time() - 100,))
            db.execute("INSERT INTO v07_samples VALUES(0,?,'ok',10)", (time.time() - 99,))
        output = self.folder / "testing.zip"
        pilot.export(self.folder, output)
        with ZipFile(output) as package:
            self.assertEqual(set(package.namelist()), {pilot.MARKER, pilot.EVIDENCE, "status.json"})
            self.assertEqual(json.loads(package.read("status.json"))["observed_ok"], 1)
            extracted = Path(package.extract(pilot.EVIDENCE, self.folder / "inspect"))
            with closing(sqlite3.connect(extracted.as_uri() + "?mode=ro", uri=True)) as restored:
                self.assertEqual(restored.execute("SELECT result FROM v07_samples").fetchall(), [("ok",)])
        with self.assertRaises(FileExistsError):
            pilot.export(self.folder, output)
