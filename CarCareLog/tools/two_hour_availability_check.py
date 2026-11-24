"""Observe a synthetic local dashboard every minute from minute 0 through minute 120."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from http.client import HTTPException
import json
import os
from pathlib import Path
import platform
import socket
import time

from short_availability_check import dashboard, pilot


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="milliseconds")


def write_event(journal, event):
    journal.write(json.dumps(event) + "\n")
    journal.flush()
    os.fsync(journal.fileno())


def collect(folder):
    # A distinct folder for each run preserves evidence from interrupted runs.
    folder.mkdir(parents=True, exist_ok=False)
    pilot.seed(folder)
    with closing(socket.socket()) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with (folder / "observations.jsonl").open("x", encoding="utf-8") as journal, pilot.running_site(folder, port) as service:
        build = pilot.fingerprint()
        protocol = {
            "protocol": "Local dashboard HTTP/SQLite fixture check, one scheduled read per minute including both endpoints",
            "interval_seconds": 60, "planned_minutes": 120, "planned_reads": 121,
            "platform": platform.system(), "python": platform.python_version(),
            "expected_vehicle_id": 1, "expected_receipts": 3, "expected_total_cents": 35999,
            "build_sha256_at_start": build, "official_seven_day_window_started": False,
        }
        write_event(journal, {"event": "start", **protocol})
        samples = []
        for minute in range(121):
            if minute:
                # Schedule subsequent probes relative to the first actual probe. A missed
                # minute has no sample; never issue catch-up HTTP requests for old slots.
                deadline = first_start + minute * 60
                while time.time() < deadline:
                    time.sleep(min(60, max(0, deadline - time.time())))
            started = time.time()
            if not minute:
                first_start = started
                deadline = started
                print(f"Start {stamp(started)}; last due {stamp(started + 7200)}; "
                      f"monitor PID {os.getpid()}; service PID {service.pid}; loopback port {port}", flush=True)
            row = {"minute": minute, "scheduled_utc": stamp(deadline)}
            if started >= deadline + 60:
                row["result"] = "missing"
            else:
                row["attempted_utc"] = stamp(started)
                row["elapsed_seconds_at_attempt"] = round(started - first_start, 3)
                try:
                    if service.poll() is not None:
                        raise ConnectionError("Fixture service exited.")
                    row.update(dashboard(port))
                    row["result"] = "ok" if row["matches_fixture"] else "incorrect-dashboard"
                except (OSError, HTTPException, ValueError, KeyError, TypeError) as exc:
                    row["result"] = "failed"
                    row["error_type"] = type(exc).__name__
            samples.append(row)
            write_event(journal, {"event": "sample", **row})
            if minute % 10 == 0 or row["result"] != "ok":
                print(f"Minute {minute}: {row['result']}", flush=True)
        attempted = [r for r in samples if "attempted_utc" in r]
        end_build = pilot.fingerprint()
        summary = {**protocol, "build_sha256_at_end": end_build,
                   "start_utc": stamp(first_start), "finished_utc": stamp(time.time()),
                   "first_to_last_attempt_seconds": attempted[-1]["elapsed_seconds_at_attempt"],
                   "successful_fixture_reads": sum(r["result"] == "ok" for r in samples),
                   "failed_reads": sum(r["result"] not in {"ok", "missing"} for r in samples),
                   "missing_reads": sum(r["result"] == "missing" for r in samples)}
        write_event(journal, {"event": "end", **summary})
        report = {**summary, "scheduled_reads": samples}
        with (folder / "two-hour-local-availability.json").open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
        print(json.dumps(summary), flush=True)
        return summary["successful_fixture_reads"] == len(samples) and build == end_build


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path, help="New run folder outside the checkout")
    args = parser.parse_args()
    target = args.workspace.resolve()
    if target == pilot.REPO or pilot.REPO in target.parents:
        parser.error("Choose a new workspace outside the checkout.")
    raise SystemExit(0 if collect(target) else 1)
