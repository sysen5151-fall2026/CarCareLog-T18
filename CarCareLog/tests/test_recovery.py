"""Exercise backups with genuine SQLite ledgers in temporary storage."""
from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from backend import app, owner_site, recovery


def add_car(path, name):
    with closing(app.connect(path)) as db, db:
        db.execute("INSERT INTO vehicles(name,mileage) VALUES(?,0)", (name,))


def cars(path):
    with closing(app.connect(path)) as db:
        return [row[0] for row in db.execute("SELECT name FROM vehicles ORDER BY id")]


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.path = self.folder / "single.sqlite3"
        self.manager = recovery.RecoveryManager.for_ledger(self.path)
        app.init_db(self.path)
        add_car(self.path, "Original")

    def test_missing_or_damaged_live_db_recovers_and_preserves_damaged_bytes(self):
        with self.manager as manager:
            manager.snapshot()
        self.path.unlink()
        with self.manager:
            self.assertEqual(cars(self.path), ["Original"])
        self.path.write_bytes(b"Damaged local test database")
        with self.manager:
            self.assertEqual(cars(self.path), ["Original"])
            self.assertTrue(any(p.read_bytes() == b"Damaged local test database"
                                for p in self.manager.archive.glob("damaged-*/single.sqlite3")))

    def test_damaged_newest_snapshot_falls_back_and_healthy_db_is_preserved(self):
        with self.manager as manager:
            manager.snapshot()
            add_car(self.path, "Newer")
            newest = manager.snapshot()
            (newest / manager.key).write_bytes(b"Not the bytes that were captured")
        with self.manager:
            self.assertEqual(cars(self.path), ["Original", "Newer"])
        self.path.unlink()
        with self.manager:
            self.assertEqual(cars(self.path), ["Original"])

    def test_explicit_failure_if_all_copies_unusable_and_wrong_schema_never_replaced(self):
        with self.manager as manager:
            latest = manager.snapshot()
        self.path.unlink()
        with closing(sqlite3.connect(self.path)) as alien:
            alien.execute("CREATE TABLE unrelated(id)")
        with self.assertRaisesRegex(recovery.RecoveryError, "Unexpected application schema"):
            with self.manager:
                pass
        (latest / "sha256.json").write_text("bad manifest")
        self.path.write_bytes(b"original damaged data")
        with self.assertRaisesRegex(recovery.RecoveryError, "No verified snapshot"):
            with self.manager:
                pass
        self.assertEqual(self.path.read_bytes(), b"original damaged data")

    def test_online_snapshot_excludes_uncommitted_transactions(self):
        with self.manager as manager, closing(app.connect(self.path)) as writer:
            writer.execute("INSERT INTO vehicles(name,mileage) VALUES('Uncommitted',12)")
            generation = manager.snapshot()
            self.assertEqual(cars(generation / manager.key), ["Original"])
            writer.rollback()

    def test_background_timer_shutdown_and_service_lock(self):
        with patch.object(recovery, "INTERVAL", 0.04):
            with self.manager as manager:
                manager.start()
                with self.assertRaises(recovery.RecoveryError):
                    with recovery.RecoveryManager.for_ledger(self.path):
                        pass
                add_car(self.path, "Captured")
                limit = time.monotonic() + 4
                while len(manager.generations()) < 2 and time.monotonic() < limit:
                    time.sleep(0.02)
                self.assertGreaterEqual(len(manager.generations()), 2)
            self.assertEqual(cars(manager.generations()[0] / manager.key), ["Original", "Captured"])
            self.assertFalse(manager.worker.is_alive())

    def test_recover_registry_and_one_owner_with_separate_records_and_fresh_login(self):
        site = owner_site.Site(self.folder, "http://127.0.0.1:8000")
        manager = recovery.RecoveryManager.for_accounts(self.folder)
        password = "only for this temporary test"
        tokens = [site.account(user, password, True) for user in ("alice", "bobby")]
        hashes = [hashlib.sha256(token.encode()).digest() for token in tokens]
        ledgers = [site.ledger(site.session(token_hash)[0]) for token_hash in hashes]
        add_car(ledgers[0], "Alice")
        add_car(ledgers[1], "Bob")
        with manager:
            manager.snapshot()
        add_car(ledgers[1], "Bob newer")
        ledgers[0].unlink()
        site.database.write_bytes(b"fixture-corruption")
        with manager:
            self.assertEqual(cars(ledgers[0]), ["Alice"])
            self.assertEqual(cars(ledgers[1]), ["Bob", "Bob newer"])
            self.assertIsNone(site.session(hashes[0]))
            self.assertIsNotNone(site.account("alice", password, False))
            self.assertIsNotNone(site.account("bobby", password, False))

    def test_failed_account_snapshot_does_not_replace_published_generation(self):
        site = owner_site.Site(self.folder, "http://127.0.0.1:8000")
        manager = recovery.RecoveryManager.for_accounts(self.folder)
        with manager:
            original = manager.snapshot()
        token = site.account("newowner", "only for temporary test", True)
        ledger = site.ledger(site.session(hashlib.sha256(token.encode()).digest())[0])
        ledger.unlink()
        with recovery.service_lock(manager.archive):
            with self.assertRaises(sqlite3.Error):
                manager.snapshot()
        self.assertEqual(manager.generations(), [original])
        with self.assertRaisesRegex(recovery.RecoveryError, "No verified snapshot"):
            with manager:
                pass
        self.assertFalse(ledger.exists())
