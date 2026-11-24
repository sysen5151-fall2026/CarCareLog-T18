"""Resume an interrupted two-hour observation on its original schedule and fixture."""
import argparse
from datetime import datetime
from http.client import HTTPException
import json
from pathlib import Path
import time

from two_hour_availability_check import dashboard, pilot, stamp, write_event


def resume(folder, port):
    source = folder / "observations.jsonl"
    rows = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines()]
    if not rows or rows[0].get("event") != "start" or any(r["event"] == "end" for r in rows):
        raise ValueError("Use an existing, unfinished observation.")
    protocol = dict(rows[0])
    del protocol["event"]
    fingerprint = pilot.fingerprint()
    if fingerprint != protocol["build_sha256_at_start"] or not (folder / "fixture" / "single-owner.sqlite3").is_file():
        raise ValueError("The original build and fixture are required.")
    samples = [{k:v for k,v in row.items() if k != "event"} for row in rows if row["event"] == "sample"]
    if not samples or [r["minute"] for r in samples] != list(range(len(samples))):
        raise ValueError("The existing journal must have a complete prefix of scheduled slots.")
    origin = datetime.fromisoformat(samples[0]["scheduled_utc"]).timestamp()
    resumes = [row["resumed_utc"] for row in rows if row["event"] == "resume"]
    with pilot.running_site(folder, port) as service, source.open("a", encoding="utf-8") as out:
        resumes.append(stamp(time.time()))
        write_event(out, {"event":"resume", "resumed_utc":resumes[-1],
                          "previous_last_recorded_minute": samples[-1]["minute"],
                          "same_fixture_and_build":True, "local_service_restarted":True})
        for minute in range(len(samples), protocol["planned_reads"]):
            deadline = origin + minute * protocol["interval_seconds"]
            while time.time() < deadline:
                time.sleep(min(60, max(0, deadline-time.time())))
            now = time.time()
            row = {"minute":minute, "scheduled_utc":stamp(deadline)}
            if now >= deadline + protocol["interval_seconds"]:
                row["result"] = "missing"
            else:
                row.update(attempted_utc=stamp(now), elapsed_seconds_at_attempt=round(now-origin,3))
                try:
                    if service.poll() is not None:
                        raise ConnectionError("Fixture process exited.")
                    row.update(dashboard(port))
                    row["result"] = "ok" if row["matches_fixture"] else "incorrect-dashboard"
                except (OSError, HTTPException, ValueError, KeyError, TypeError) as exc:
                    row.update(result="failed",error_type=type(exc).__name__)
            samples.append(row)
            write_event(out, {"event":"sample", **row})
            print(f"Minute {minute}: {row['result']}", flush=True)
        attempted = [r for r in samples if "attempted_utc" in r]
        summary = {**protocol, "build_sha256_at_end":pilot.fingerprint(), "start_utc":stamp(origin),
                   "finished_utc":stamp(time.time()), "resume_events_utc":resumes,
                   "service_restarted_on_resume":True,
                   "first_to_last_attempt_seconds":attempted[-1]["elapsed_seconds_at_attempt"],
                   "successful_fixture_reads":sum(r["result"]=="ok" for r in samples),
                   "failed_reads":sum(r["result"] not in {"ok","missing"} for r in samples),
                   "missing_reads":sum(r["result"]=="missing" for r in samples)}
        write_event(out, {"event":"end", **summary})
        with (folder / "two-hour-local-availability.json").open("x", encoding="utf-8") as evidence:
            json.dump({**summary,"scheduled_reads":samples},evidence,indent=2)
            evidence.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--port", required=True, type=int)
    args = parser.parse_args()
    directory = args.workspace.resolve()
    with pilot.service_lock(directory / ".resume-lock"):
        resume(directory, args.port)
