"""V07: observe a local CarCareLog dashboard once per minute for seven days."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
import sqlite3
import time


MINUTES = 7 * 24 * 60
MIN_PASS = (99 * MINUTES + 99) // 100


def core_read(port, vehicle_id, timeout=5):
    connection = HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        connection.request("GET", f"/api/dashboard?vehicle_id={vehicle_id}")
        response = connection.getresponse()
        if response.status != 200:
            return f"http-{response.status}"
        data = json.loads(response.read(2_000_001))
        vehicle = data["vehicle"]
        rows = data["records"]
        if (vehicle["id"] != vehicle_id or not isinstance(rows, list) or not rows
                or not all(row["vehicle_id"] == vehicle_id for row in rows)
                or data["total_cents"] != sum(row["cost_cents"] for row in rows)):
            return "wrong-dashboard"
        return "ok"
    except (OSError, HTTPException):
        return "unreachable"
    except (ValueError, TypeError, KeyError, UnicodeError):
        return "invalid-dashboard"
    finally:
        connection.close()


def configure(db, port, vehicle_id):
    # The write lock also serializes first launch by two processes on the same file.
    with db:
        db.execute("BEGIN IMMEDIATE")
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and tables != {"v07_pilot", "v07_samples"}:
            raise ValueError("Choose a dedicated V07 evidence file.")
        db.execute("""CREATE TABLE IF NOT EXISTS v07_pilot
                      (id INTEGER PRIMARY KEY CHECK (id=1), start REAL NOT NULL, port INTEGER NOT NULL,
                       vehicle_id INTEGER NOT NULL)""")
        db.execute("""CREATE TABLE IF NOT EXISTS v07_samples
                      (slot INTEGER PRIMARY KEY, observed REAL NOT NULL, result TEXT, latency_ms INTEGER)""")
        config = db.execute("SELECT start,port,vehicle_id FROM v07_pilot WHERE id=1").fetchone()
        if config:
            if (port is not None and port != config[1]) or (vehicle_id is not None and vehicle_id != config[2]):
                raise ValueError("The recorded port and fixture vehicle cannot change during this pilot.")
            return config
        config = (time.time(), 8000 if port is None else port, 1 if vehicle_id is None else vehicle_id)
        db.execute("INSERT INTO v07_pilot VALUES (1,?,?,?)", config)
        return config


def observe(db, config, now=None, clock=time.time, read=core_read):
    """Claim the current real minute only. An interrupted claim cannot be replayed."""
    start, port, vehicle_id = config
    now = clock() if now is None else now
    slot = int((now - start) // 60)
    if not 0 <= slot < MINUTES:
        return
    with db:
        inserted = db.execute("INSERT OR IGNORE INTO v07_samples(slot,observed) VALUES(?,?)", (slot, now))
    if inserted.rowcount == 0:
        return
    deadline = start + (slot + 1) * 60
    began = time.monotonic()
    remaining = deadline - clock()
    result = read(port, vehicle_id, min(5, remaining)) if remaining > 0 else "late"
    elapsed = round((time.monotonic() - began) * 1000)
    if clock() >= deadline:
        result = "late"
    with db:
        db.execute("UPDATE v07_samples SET result=?,latency_ms=? WHERE slot=?", (result, elapsed, slot))


def report(db, now):
    config = db.execute("SELECT start,port,vehicle_id FROM v07_pilot WHERE id=1").fetchone()
    if not config:
        raise ValueError("The evidence file has no pilot.")
    start, port, vehicle_id = config
    elapsed = max(0, min(MINUTES, int((now - start) // 60)))
    # Report only fully elapsed minutes; a sample in the open minute is provisional.
    ok, failed = db.execute("""SELECT count(CASE WHEN result='ok' THEN 1 END),
                               count(CASE WHEN result IS NOT NULL AND result!='ok' THEN 1 END)
                               FROM v07_samples WHERE slot < ?""", (elapsed,)).fetchone()
    complete = elapsed == MINUTES
    return {
        "start_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "end_utc": datetime.fromtimestamp(start + MINUTES * 60, timezone.utc).isoformat(),
        "loopback_port": port, "fixture_vehicle_id": vehicle_id,
        "scheduled_total": MINUTES, "completed_minutes": elapsed, "observed_ok": ok,
        "observed_failed": failed, "missing_or_interrupted": elapsed - ok - failed,
        "successful_percent_of_elapsed": round(100 * ok / elapsed, 3) if elapsed else None,
        "minimum_successes": MIN_PASS,
        "v07": ("pass" if ok >= MIN_PASS else "fail") if complete else "pending",
    }


def collect(db, config):
    start = config[0]
    end = start + MINUTES * 60
    print("Collecting from the synthetic vehicle dashboard. Ctrl+C stops the monitor. Resume with the same evidence file.",
          flush=True)
    while time.time() < end:
        now = time.time()
        observe(db, config, now)
        next_slot = max(0, int((now - start) // 60) + 1)
        sleep_for = min(end, start + next_slot * 60) - time.time()
        if sleep_for > 0:
            time.sleep(min(60, sleep_for))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="one readiness read; records no pilot data")
    monitor = commands.add_parser("monitor", help="start or resume the foreground seven-day pilot")
    summary = commands.add_parser("status", help="show counts and the current verdict")
    for sub in (monitor, summary):
        sub.add_argument("evidence", type=Path, help="path to a local V07 evidence SQLite file")
    for sub in (check, monitor):
        sub.add_argument("--port", type=int, help="localhost app port (default 8000)")
        sub.add_argument("--vehicle-id", type=int, help="seeded synthetic fixture vehicle ID (default 1)")
    args = parser.parse_args()
    port, vehicle = getattr(args, "port", None), getattr(args, "vehicle_id", None)
    if (port is not None and not 1 <= port <= 65535) or (vehicle is not None and vehicle < 1):
        parser.error("Use a valid TCP port and positive vehicle ID.")
    if args.command == "check":
        outcome = core_read(port or 8000, vehicle or 1)
        print(f"Single readiness read: {outcome}. V07 requires a separate consecutive seven-day pilot.")
        return 0 if outcome == "ok" else 1
    path = args.evidence.expanduser().resolve()
    try:
        if args.command == "status":
            connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        else:
            connection = sqlite3.connect(path, timeout=10)
        with closing(connection) as db:
            if args.command == "monitor":
                config = configure(db, port, vehicle)
                try:
                    collect(db, config)
                except KeyboardInterrupt:
                    pass
            print(json.dumps(report(db, time.time()), indent=2))
    except (OSError, sqlite3.Error, ValueError) as error:
        parser.exit(1, f"V07 evidence: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
