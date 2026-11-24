"""Local SQLite snapshots and offline startup recovery for CarCareLog."""
from contextlib import closing, contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import threading
import time
from uuid import uuid4


LOG = logging.getLogger(__name__)
OWNER = re.compile(r"[0-9a-f]{32}")
SNAPSHOT = re.compile(r"snapshot-[0-9]{20}-[0-9a-f]{8}")
INTERVAL = 3600
RETENTION = 24


class RecoveryError(RuntimeError):
    """A local operator needs to check the storage before continuing."""


class DamagedDatabase(RecoveryError):
    """A missing, empty or corrupt database may be repaired from a valid copy."""


def digest(path):
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def existing_db(path, writable=False):
    return sqlite3.connect(path.as_uri() + ("?mode=rw" if writable else "?mode=ro"), uri=True, timeout=5)


def check_db(path, accounts=False, writable=False):
    if not path.exists() or path.stat().st_size == 0:
        raise DamagedDatabase("Database is missing or empty.")
    try:
        with closing(existing_db(path, writable)) as db:
            if db.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise DamagedDatabase("SQLite integrity check failed.")
            tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            expected = {"owners", "sessions"} if accounts else {"vehicles", "records", "reminders"}
            if not expected.issubset(tables):
                raise RecoveryError(f"Unexpected application schema at {path}. Check the selected data location.")
            if db.execute("PRAGMA foreign_key_check").fetchone():
                raise DamagedDatabase("Database contains broken references.")
    except sqlite3.DatabaseError as exc:
        # Operational errors (read-only media, locks, unavailable disk) must not trigger replacement.
        code = getattr(exc, "sqlite_errorcode", 0) & 255
        if code in (11, 26) or str(exc) in {"file is not a database", "database disk image is malformed"}:
            raise DamagedDatabase("SQLite reported a damaged database.") from exc
        raise


def owner_ledgers(registry):
    with closing(existing_db(registry)) as db:
        ids = [row[0] for row in db.execute("SELECT id FROM owners ORDER BY id")]
    if not all(isinstance(value, str) and OWNER.fullmatch(value) for value in ids):
        raise RecoveryError("Unexpected owner ledger identifier.")
    return [f"ledgers/{value}.sqlite3" for value in ids]


def copy_database(source, target, accounts=False):
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    deadline = time.monotonic() + 60

    def budget(status, remaining, total):
        if time.monotonic() >= deadline:
            raise RecoveryError("SQLite backup timed out. The last published snapshot is preserved.")

    with closing(existing_db(source)) as live, closing(sqlite3.connect(target)) as copy:
        live.backup(copy, pages=128, sleep=0.1, progress=budget)
        copy.execute("PRAGMA journal_mode=DELETE")
        if accounts:
            # Restoring a registry must never revive logged-out sessions.
            copy.execute("PRAGMA secure_delete=ON")
            copy.execute("DELETE FROM sessions")
            copy.commit()
    check_db(target, accounts)


@contextmanager
def service_lock(folder):
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (folder / "service.lock").open("a+b") as stream:
        if os.name == "nt":
            import msvcrt
            if stream.seek(0, 2) == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            lock = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            unlock = lambda: msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            lock = lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            unlock = lambda: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        try:
            lock()
        except OSError as exc:
            raise RecoveryError("Could not lock the data location. Stop the other CarCareLog instance before restoring.") from exc
        try:
            yield
        finally:
            unlock()


class RecoveryManager:
    def __init__(self, database, accounts):
        self.database = Path(database).expanduser().resolve()
        self.accounts = accounts
        self.key = "accounts.sqlite3" if accounts else "ledger.sqlite3"
        suffix = "accounts" if accounts else "ledger-" + self.database.name
        self.archive = self.database.parent / (".carcare-recovery-" + suffix)
        self.stop_event = threading.Event()
        self.worker = None

    @classmethod
    def for_ledger(cls, path):
        return cls(path, False)

    @classmethod
    def for_accounts(cls, folder):
        return cls(Path(folder) / "accounts.sqlite3", True)

    def generations(self):
        return sorted((p for p in self.archive.iterdir() if p.is_dir() and SNAPSHOT.fullmatch(p.name)), reverse=True)

    def snapshot(self):
        """Publish only after all copied databases pass validation; require the service lock."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        location = self.archive / f"snapshot-{stamp}-{uuid4().hex[:8]}"
        with tempfile.TemporaryDirectory(dir=self.archive, prefix=".work-") as temp:
            stage = Path(temp) / "snapshot"
            copy_database(self.database, stage / self.key, self.accounts)
            keys = [self.key]
            if self.accounts:
                for key in owner_ledgers(stage / self.key):
                    copy_database(self.database.parent / key, stage / key)
                    keys.append(key)
            checksums = {key: digest(stage / key) for key in keys}
            (stage / "sha256.json").write_text(json.dumps(checksums, sort_keys=True), encoding="utf-8")
            stage.rename(location)
        for old in self.generations()[RETENTION:]:
            shutil.rmtree(old)
        return location

    def restore_if_damaged(self, target, key):
        registry = self.accounts and key == self.key
        try:
            check_db(target, registry, writable=True)
            return
        except DamagedDatabase as fault:
            reason = str(fault)
        for candidate in self.generations():
            source = candidate / key
            try:
                checksums = json.loads((candidate / "sha256.json").read_text(encoding="utf-8"))
                if not isinstance(checksums, dict) or key not in checksums or digest(source) != checksums[key]:
                    continue
                check_db(source, registry)
            except (FileNotFoundError, ValueError, sqlite3.DatabaseError, RecoveryError):
                continue
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            # Same-volume staging keeps publishing atomic even after a short write or full disk.
            with tempfile.TemporaryDirectory(dir=target.parent) as staging:
                replacement = Path(staging) / "replacement"
                shutil.copyfile(source, replacement)
                replacement.chmod(0o600)
                if digest(replacement) != checksums[key]:
                    raise RecoveryError("Restored bytes failed their checksum.")
                preserved = self.archive / ("damaged-" + uuid4().hex)
                preserved.mkdir(mode=0o700)
                if target.exists():
                    shutil.copy2(target, preserved / target.name)
                for suffix in ("-wal", "-shm", "-journal"):
                    sidecar = Path(str(target) + suffix)
                    if sidecar.exists():
                        sidecar.replace(preserved / sidecar.name)
                replacement.replace(target)
            check_db(target, registry)
            LOG.warning("Recovered %s from %s. Preserved damaged files in %s.", target, candidate.name, preserved)
            captured = datetime.strptime(candidate.name.split("-")[1], "%Y%m%d%H%M%S%f").replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - captured).total_seconds() / 3600
            if age_hours > 24:
                LOG.warning("The restored backup is %.1f hours old and exceeds the 24-hour recovery-point target.", age_hours)
            return
        raise RecoveryError(f"{target}: {reason} No verified snapshot was found. Original data retained.")

    def recover(self):
        # Recognize a first launch without turning a previously recorded loss into an empty workspace.
        if not self.database.exists() and not self.generations():
            if self.accounts and any((self.database.parent / "ledgers").glob("*.sqlite3")):
                raise RecoveryError("Owner ledgers exist but their registry and snapshots are missing.")
            return
        self.restore_if_damaged(self.database, self.key)
        if self.accounts:
            for key in owner_ledgers(self.database):
                self.restore_if_damaged(self.database.parent / key, key)

    def __enter__(self):
        self.lock = service_lock(self.archive)
        self.lock.__enter__()
        try:
            self.recover()
        except BaseException:
            self.lock.__exit__(None, None, None)
            raise
        return self

    def start(self):
        self.snapshot()
        self.worker = threading.Thread(target=self._run, name="carcare-backup", daemon=True)
        self.worker.start()

    def _run(self):
        while not self.stop_event.wait(INTERVAL):
            try:
                self.snapshot()
            except (OSError, sqlite3.Error, RecoveryError):
                LOG.exception("Periodic backup failed. The previous complete snapshot is retained.")

    def __exit__(self, exc_type, exc, traceback):
        try:
            if self.worker:
                self.stop_event.set()
                self.worker.join()
                if exc_type is None or exc_type is KeyboardInterrupt:
                    self.snapshot()
        finally:
            self.lock.__exit__(exc_type, exc, traceback)
