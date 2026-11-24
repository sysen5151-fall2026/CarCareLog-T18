"""Measure backup-point age and restart-to-readable-data time using disposable local ledgers."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "CarCareLog"))
from backend import app, owner_site
from backend.recovery import INTERVAL, RecoveryManager


def get_time():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def request(port, method, path, form=None, cookie=None):
    headers = {"Origin": f"http://127.0.0.1:{port}", "Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = cookie
    with closing(HTTPConnection("127.0.0.1", port, timeout=1)) as connection:
        body = json.dumps(form).encode() if form is not None else None
        connection.request(method, path, body, headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read()), response.getheader("Set-Cookie")


def measure(accounts):
    # Every fault in this drill is confined to a new TemporaryDirectory.
    with TemporaryDirectory(prefix="carcare-recovery-drill-") as temp:
        folder = Path(temp)
        with closing(socket.socket()) as free:
            free.bind(("127.0.0.1", 0))
            port = free.getsockname()[1]
        registry_dir = folder / "accounts"
        password = "synthetic drill passphrase"
        if accounts:
            site = owner_site.Site(registry_dir, f"http://127.0.0.1:{port}")
            token = site.account("first-owner", password, True)
            site.account("other-owner", password, True)
            ledger = site.ledger(site.session(hashlib.sha256(token.encode()).digest())[0])
            manager = RecoveryManager.for_accounts(registry_dir)
        else:
            ledger = folder / "single-owner.sqlite3"
            app.init_db(ledger)
            manager = RecoveryManager.for_ledger(ledger)
        with closing(app.connect(ledger)) as db, db:
            app.seed_demo(db)
        with manager:
            capture_start = time.monotonic()
            capture_time = get_time()
            manager.snapshot()
        with closing(app.connect(ledger)) as db, db:
            db.execute("INSERT INTO vehicles(name,mileage) VALUES('After snapshot',0)")
        failure_start = time.monotonic()
        failure_time = get_time()
        ledger.write_bytes(b"damaged synthetic ledger")
        if accounts:
            site.database.unlink()
        args = [sys.executable, str(REPO / "run_demo.py"), "--data-dir", str(folder), "--port", str(port)]
        if accounts:
            args.append("--accounts")
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            while time.monotonic() - failure_start < 20:
                if process.poll() is not None:
                    raise RuntimeError("Demo failed to start: " + process.stderr.read())
                try:
                    path = "/health" if accounts else "/api/vehicles"
                    if request(port, "GET", path)[0] == 200:
                        break
                except OSError:
                    pass
                time.sleep(0.02)
            cookie = None
            if accounts:
                status, _, other_cookie = request(port, "POST", "/api/auth/login",
                                                  {"username": "other-owner", "password": password})
                if status != 200 or request(port, "GET", "/api/vehicles", cookie=other_cookie.split(";")[0])[1] != []:
                    raise ValueError("The second owner's records were not isolated.")
                status, _, auth = request(port, "POST", "/api/auth/login",
                                          {"username": "first-owner", "password": password})
                if status != 200:
                    raise ValueError("Recovered owner could not sign in.")
                cookie = auth.split(";")[0]
            status, cars, _ = request(port, "GET", "/api/vehicles", cookie=cookie)
            if status != 200 or len(cars) != 1 or cars[0]["name"] == "After snapshot":
                raise ValueError("Recovered vehicles do not match the captured generation.")
            status, dashboard, _ = request(port, "GET", "/api/dashboard?vehicle_id=1", cookie=cookie)
            if status != 200 or len(dashboard.get("records", [])) != 3 or dashboard.get("total_cents") != 35999:
                raise ValueError("Recovered dashboard did not match the original receipt count and total.")
            finished = time.monotonic()
            point_age = failure_start - capture_start
            duration = finished - failure_start
            return {"mode": "local_accounts" if accounts else "single_owner",
                    "fault": "corrupt ledger and missing account registry" if accounts else "corrupt ledger",
                    "snapshot_capture_began_utc": capture_time, "fault_injected_utc": failure_time,
                    "http_validation_completed_utc": get_time(),
                    "backup_point_age_seconds_upper_bound": round(point_age, 4),
                    "incident_to_verified_http_seconds": round(duration, 4),
                    "backup_point_within_24_hours": point_age <= 86400,
                    "recovery_within_24_hours": duration <= 86400,
                    "confirmed_receipts": 3, "confirmed_total_cents": 35999,
                    "post_snapshot_write_lost_as_expected": True,
                    "isolated_second_account_verified": True if accounts else None}
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"fixture": "fresh disposable directory, synthetic demo receipts, recent completed snapshot",
              "python": platform.python_version(), "platform": platform.system(),
              "scheduled_interval_seconds_while_running": INTERVAL,
              "results": [measure(False), measure(True)]}
    result = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(result + "\n", encoding="utf-8")
    print(result)


if __name__ == "__main__":
    main()
