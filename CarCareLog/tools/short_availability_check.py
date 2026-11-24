"""Three live dashboard checks and a separate planned restart. No official V07 window is opened."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from http.client import HTTPConnection
import json
from pathlib import Path
import platform
import socket
import sys
from tempfile import TemporaryDirectory
import time

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import run_availability_pilot as pilot


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def dashboard(port):
    began = time.monotonic()
    stamp = utc_now()
    with closing(HTTPConnection("127.0.0.1", port, timeout=5)) as client:
        client.request("GET", "/api/dashboard?vehicle_id=1")
        response = client.getresponse()
        data = json.loads(response.read())
    records = data["records"]
    correct = (response.status == 200 and data["vehicle"]["id"] == 1 and len(records) == 3
               and all(r["vehicle_id"] == 1 for r in records)
               and data["total_cents"] == sum(r["cost_cents"] for r in records) == 35999)
    return {"observed_utc": stamp, "http_status": response.status, "vehicle_id": data["vehicle"]["id"],
            "receipt_count": len(records), "total_cents": data["total_cents"],
            "matches_fixture": correct, "latency_ms": round(1000 * (time.monotonic() - began), 2)}


def measure():
    with TemporaryDirectory(prefix="carcare-short-observation-") as tmp:
        folder = Path(tmp)
        with closing(socket.socket()) as free:
            free.bind(("127.0.0.1", 0))
            port = free.getsockname()[1]
        pilot.seed(folder)
        fingerprint = pilot.fingerprint()
        with pilot.running_site(folder, port):
            start = time.monotonic()
            reads = []
            for slot in range(3):
                delay = start + slot * 60 - time.monotonic()
                if delay > 0:
                    time.sleep(min(60, delay))
                observed_at = time.monotonic()
                result = dashboard(port)
                result["seconds_from_first_scheduled_read"] = round(observed_at - start, 3)
                reads.append(result)
                print(f"Observed {len(reads)}/3: {result['observed_utc']} match={result['matches_fixture']}", flush=True)
        stopped_at = utc_now()
        offline = pilot.study.core_read(port, 1, timeout=2)
        restarting = time.monotonic()
        with pilot.running_site(folder, port):
            restored = dashboard(port)
            restart_seconds = round(time.monotonic() - restarting, 3)
        return {"protocol": "Three real reads on a disposable synthetic dashboard, one minute apart; separate planned restart",
                "platform": platform.system(), "python": platform.python_version(), "build_sha256_at_start": fingerprint,
                "build_sha256_at_end": pilot.fingerprint(), "successful_fixture_reads": sum(r["matches_fixture"] for r in reads),
                "elapsed_first_to_last_seconds": round(reads[-1]["seconds_from_first_scheduled_read"] -
                                                      reads[0]["seconds_from_first_scheduled_read"], 3),
                "scheduled_reads": reads, "planned_restart": {"service_stopped_utc": stopped_at,
                    "offline_probe_result": offline, "restart_to_validated_dashboard_seconds": restart_seconds,
                    "restored_dashboard": restored}, "official_seven_day_window_started": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = measure()
    raw = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(raw + "\n", encoding="utf-8")
    print(raw)
    return 0 if (report["successful_fixture_reads"] == 3 and
                 report["planned_restart"]["offline_probe_result"] == "unreachable" and
                 report["planned_restart"]["restored_dashboard"]["matches_fixture"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
