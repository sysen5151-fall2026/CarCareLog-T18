"""Repeat the Chapter 10 UC.1 comparison against an isolated local service."""

import argparse
import csv
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import perf_counter_ns
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import app


class QuietHandler(app.Handler):
    def log_message(self, *_):
        pass


def request(port, method, route, payload=None):
    headers = {"X-CarCare-Timing": "1"}
    body = None
    if payload is not None:
        body = json.dumps(payload)
        headers["Content-Type"] = "application/json"
    start = perf_counter_ns()
    with closing(HTTPConnection("127.0.0.1", port, timeout=10)) as conn:
        conn.request(method, route, body, headers)
        response = conn.getresponse()
        parsed = json.loads(response.read())
        end = perf_counter_ns()
        assert response.status == (201 if method == "POST" else 200), parsed
        timings = dict(item.strip().split(";dur=")
                       for item in response.getheader("Server-Timing").split(","))
    return parsed, start, end, {key: float(val) for key, val in timings.items()}


def ms(start, end):
    return (end - start) / 1_000_000


def trial(port, pair, scenario, vehicle_id, origin, base_dashboard):
    record = {
        "vehicle_id": vehicle_id, "service_date": date.today().isoformat(),
        "service_item": "Oil change", "category": "Maintenance",
        "mileage": 52000, "cost": "89.99", "provider": "Controlled bench fixture",
        "notes": "Chapter 10 measured replay", "owner_confirmed": True,
        "operation_id": str(uuid4()),
    }
    trace = {}
    def call(label, method, path, payload=None):
        data, start, end, stages = request(port, method, path, payload)
        trace[label] = (start, end, stages)
        return data
    save = call("post", "POST", "/api/records" +
                ("?include=dashboard" if scenario == "A" else ""), record)
    if scenario == "B":
        vehicles = call("vehicles", "GET", "/api/vehicles")
        assert any(v["id"] == vehicle_id for v in vehicles)
        dashboard = call("dashboard", "GET", f"/api/dashboard?vehicle_id={vehicle_id}")
    else:
        dashboard = save["dashboard"]
    assert dashboard["total_cents"] == base_dashboard["total_cents"] + 8999
    assert len(dashboard["records"]) == len(base_dashboard["records"]) + 1
    saved_id = save["id"]
    assert any(r["id"] == saved_id and r["service_item"] == "Oil change"
               for r in dashboard["records"])
    assert dashboard["vehicle"]["mileage"] == 52000
    row = {"pair": pair, "scenario": scenario,
           "request_count": len(trace),
           "wall_ms": ms(trace["post"][0], list(trace.values())[-1][1]),
           "saved_record_id": saved_id, "dashboard_cost_cents": dashboard["total_cents"],
           "dashboard_record_count": len(dashboard["records"])}
    with closing(app.connect()) as db:
        persisted = app.dashboard(db, vehicle_id)
        assert dashboard == persisted
    for label, (start, end, stages) in trace.items():
        row.update({f"{label}_start_ms": ms(origin, start),
                    f"{label}_end_ms": ms(origin, end),
                    f"{label}_wall_ms": ms(start, end)})
        row.update({f"{label}_{stage}_ms": value for stage, value in stages.items()})
    return row, dashboard


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Folder for the new run's evidence")
    out = parser.parse_args().output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with TemporaryDirectory(prefix="bench-", dir=out) as temp:
        temp = Path(temp)
        fixture = temp / "fixture.db"
        app.DB_PATH = fixture
        app.init_db()
        with closing(app.connect()) as db, db:
            vehicle_id = app.seed_demo(db)
            base = app.dashboard(db, vehicle_id)
        with app.ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                origin = perf_counter_ns()
                started = datetime.now(timezone.utc).isoformat()
                for pair in range(41):
                    order = ("B", "A") if pair % 2 else ("A", "B")
                    dashboards = []
                    for scenario in order:
                        app.DB_PATH = temp / f"{pair}-{scenario}.db"
                        shutil.copyfile(fixture, app.DB_PATH)
                        row, dashboard = trial(server.server_port, pair, scenario, vehicle_id,
                                               origin, base)
                        dashboards.append(dashboard)
                        if pair:
                            rows.append(row)
                    assert dashboards[0] == dashboards[1]
                source_db = app.DB_PATH
                app.DB_PATH = temp / "restored.db"
                with closing(sqlite3.connect(source_db)) as src, closing(app.connect()) as dst:
                    src.backup(dst)
                    assert dst.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                restored, *_ = request(server.server_port, "GET",
                                       f"/api/dashboard?vehicle_id={vehicle_id}")
                assert restored == dashboard
            finally:
                server.shutdown()
                thread.join()
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with (out / "T18_Measured_Product_Raw.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fields)
        writer.writeheader()
        writer.writerows(rows)
    (out / "T18_Measurement_Run_Info.txt").write_text(
        f"UTC start {started}\nPython {sys.version.split()[0]}\n"
        "40 measured paired trials, 1 excluded warm-up pair, alternating order.\n"
        "Each trial copied the same initialized demo SQLite file. HTTP client and server "
        "ran on loopback in one Python process, one request at a time. Each request "
        "opened a separate HTTP connection as defined by this harness.\n"
        "Each pair produced equal dashboards. All 80 records persisted. An isolated "
        "SQLite backup restore passed integrity and exact dashboard checks.\n"
        "The bench clock starts at HTTP request initiation and ends after response "
        "decoding. It excludes browser rendering, owner entry and owner review. "
        "Server-Timing fields report stage durations on the server clock.\n",
        encoding="utf-8")
    print(f"{len(rows)} product trials verified. Isolated restore verified.")


if __name__ == "__main__":
    main()
