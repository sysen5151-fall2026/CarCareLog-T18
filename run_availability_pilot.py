"""Launch the real seven-day dashboard pilot on one designated PC, or run a one-read rehearsal."""
import argparse
from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from zipfile import ZIP_DEFLATED, ZipFile

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "CarCareLog"))
sys.path.insert(0, str(REPO / "CarCareLog" / "tools"))
import availability_study as study
from backend import app
from backend.recovery import RecoveryError, service_lock

MARKER = "pilot-identity.json"
EVIDENCE = "v07-observations.sqlite3"


def fingerprint():
    files = [Path(__file__), REPO / "run_demo.py", Path(study.__file__)]
    files.extend((REPO / "CarCareLog/backend").glob("*.py"))
    files.extend(p for p in (REPO / "CarCareLog/frontend").iterdir() if p.suffix in {".js", ".css", ".html"})
    sha = hashlib.sha256()
    for path in sorted(files):
        sha.update(path.relative_to(REPO).as_posix().encode() + b"\0")
        sha.update(hashlib.sha256(path.read_bytes()).digest())
    return sha.hexdigest()


def seed(folder):
    data = folder / "fixture"
    ledger = data / "single-owner.sqlite3"
    if ledger.exists():
        raise ValueError("The new pilot fixture already contains a database.")
    app.init_db(ledger)
    with closing(app.connect(ledger)) as db, db:
        if app.seed_demo(db) != 1:
            raise ValueError("Expected fixture vehicle 1.")


def available_port(port):
    with closing(socket.socket()) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ValueError(f"Cannot reserve loopback port {port}. A new pilot can use --port with another free port.") from exc


@contextmanager
def running_site(folder, port):
    # Refuse an occupied port before opening or seeding any site listening there.
    available_port(port)
    log = folder / "site.log"
    with log.open("ab") as output:
        args = [sys.executable, str(REPO / "run_demo.py"), "--port", str(port),
                "--data-dir", str(folder / "fixture")]
        process = subprocess.Popen(args, stdout=output, stderr=output,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        try:
            end = time.monotonic() + 15
            while time.monotonic() < end:
                if process.poll() is not None:
                    raise ValueError(f"Fixture service did not start. Read {log}.")
                if study.core_read(port, 1, timeout=1) == "ok" and process.poll() is None:
                    break
                time.sleep(0.1)
            else:
                raise ValueError(f"Readiness check failed. Read {log}.")
            yield process
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


def identity(folder, port):
    marker = folder / MARKER
    if marker.exists():
        saved = json.loads(marker.read_text(encoding="utf-8"))
        if saved.get("schema") != 1 or saved["build_sha256"] != fingerprint():
            raise ValueError("Resume using the same extracted release that started this pilot.")
        if saved["machine"] != platform.node():
            raise ValueError("Resume on the computer that started this pilot.")
        if port is not None and saved["port"] != port:
            if (folder / EVIDENCE).exists():
                raise ValueError("Resume on the original port.")
            available_port(port)
            saved["port"] = port
            marker.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
        if not (folder / "fixture" / "single-owner.sqlite3").is_file():
            raise ValueError("The original pilot ledger is missing. Preserve its evidence and investigate.")
        return saved
    if any(p.name != ".pilot-lock" for p in folder.iterdir()):
        raise ValueError("Choose a dedicated empty directory for a new pilot.")
    available_port(port or 8017)
    seed(folder)
    saved = {"schema": 1, "build_sha256": fingerprint(), "machine": platform.node(),
             "platform": platform.platform(), "python": platform.python_version(),
             "port": port or 8017, "vehicle_id": 1}
    marker.write_text(json.dumps(saved, indent=2) + "\n", encoding="utf-8")
    return saved


def read_status(folder):
    with closing(sqlite3.connect((folder / EVIDENCE).as_uri() + "?mode=ro", uri=True)) as db:
        return study.report(db, time.time())


def run_pilot(folder, port):
    folder.mkdir(parents=True, exist_ok=True)
    with service_lock(folder / ".pilot-lock"):
        info = identity(folder, port)
        evidence = folder / EVIDENCE
        if evidence.exists() and read_status(folder)["v07"] != "pending":
            print(json.dumps(read_status(folder), indent=2))
            return
        with running_site(folder, info["port"]) as process, closing(sqlite3.connect(evidence, timeout=10)) as db:
            config = study.configure(db, info["port"], 1)
            print(json.dumps(study.report(db, time.time()), indent=2), flush=True)
            def read(port, vehicle_id, timeout):
                if process.poll() is not None:
                    return "fixture-process-exited"
                return study.core_read(port, vehicle_id, timeout)
            try:
                study.collect(db, config, read=read)
            except KeyboardInterrupt:
                print("Stopped. Use the same run command on this computer to resume the original window.")
            print(json.dumps(study.report(db, time.time()), indent=2))


def export(folder, output):
    # Back up the evidence first, so counts and raw rows in the ZIP describe the same instant.
    with TemporaryDirectory() as tmp:
        copy = Path(tmp) / EVIDENCE
        with closing(sqlite3.connect((folder / EVIDENCE).as_uri() + "?mode=ro", uri=True)) as live:
            with closing(sqlite3.connect(copy)) as snapshot:
                live.backup(snapshot)
                summary = study.report(snapshot, time.time())
        with ZipFile(output, "x", ZIP_DEFLATED) as package:
            package.write(copy, EVIDENCE)
            package.write(folder / MARKER, MARKER)
            package.writestr("status.json", json.dumps(summary, indent=2) + "\n")
    print(f"{summary['v07']}: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "run", "status", "export"))
    parser.add_argument("--workspace", type=Path, default=Path.home() / "CarCareLog-V07-Pilot")
    parser.add_argument("--port", type=int, help="default 8017; choose another free port before first launch")
    parser.add_argument("--output", type=Path, help="new ZIP path for export")
    args = parser.parse_args()
    folder = args.workspace.expanduser().resolve()
    if folder == REPO or REPO in folder.parents:
        parser.error("Keep pilot data outside the repository.")
    if args.port is not None and not 1 <= args.port <= 65535:
        parser.error("Port must be 1 through 65535.")
    if args.action == "export" and not args.output:
        parser.error("Specify --output for the evidence ZIP.")
    try:
        if args.action == "check":
            with TemporaryDirectory(prefix="carcare-v07-check-") as tmp:
                fixture = Path(tmp)
                seed(fixture)
                with running_site(fixture, args.port or 8017):
                    print("Readiness passed: one real HTTP dashboard read with synthetic receipts. No official window started.")
        elif args.action == "run":
            run_pilot(folder, args.port)
        elif args.action == "status":
            print(json.dumps(read_status(folder), indent=2))
        else:
            export(folder, args.output)
    except (OSError, sqlite3.Error, RecoveryError, ValueError, KeyError) as error:
        parser.exit(1, f"V07: {error}\n")


if __name__ == "__main__":
    main()
