"""Lab 13.5 clean-machine smoke test: the primary use case end to end.

    python CarCareLog/tools/smoke_test.py               # stub model runtime, no Ollama needed
    python CarCareLog/tools/smoke_test.py --real-model  # pinned model in a running Ollama

It starts the real application as a separate process on a free port with a temporary
database, then walks the demonstration script through the HTTP API the page uses:
demo data -> receipt text -> local model draft -> owner Confirm & save -> dashboard,
restart and persistence, and the R2 fallback when the runtime is unavailable.
The stub stands in only for Ollama's /api/generate; everything else is the product.
"""

import argparse
from contextlib import ExitStack, closing, contextmanager
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from threading import Thread
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "CarCareLog" / "backend" / "app.py"
DEMO_RECEIPT = ROOT / "CarCareLog" / "data" / "demo-receipt.txt"
SAMPLES = ROOT / "CarCareLog" / "data" / "receipt-samples.jsonl"
sys.path.insert(0, str(ROOT / "CarCareLog"))
from backend.receipt_runtime import PINNED_MODEL, ReceiptRuntimeUnavailable, runtime_details  # noqa: E402

STARTUP_TIMEOUT = 120


def free_port():
    with closing(socket.socket()) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class StubRuntime(BaseHTTPRequestHandler):
    """Answers like Ollama, returning the labeled ideal draft for a known sample receipt."""
    drafts = {}

    def log_message(self, *_):
        pass

    def send(self, payload):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.send({"version": "stub"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.path == "/api/generate":
            text = json.loads(body["prompt"].rsplit("Receipt text (JSON string): ", 1)[1])
            draft = self.drafts.get(text.strip(), dict.fromkeys(
                ("service_date", "service_item", "category", "odometer_value", "odometer_unit", "cost", "provider")))
            return self.send({"model": body["model"], "response": json.dumps(draft), "done": True})
        self.send({"details": {"family": "stub"}, "modelfile": ""})


@contextmanager
def stub_runtime():
    with open(SAMPLES, encoding="utf-8") as handle:
        StubRuntime.drafts = {s["text"].strip(): s["ideal_draft"] for s in map(json.loads, handle) if s}
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubRuntime)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        server.server_close()


class App:
    def __init__(self, env):
        self.port = free_port()
        self.env = {**os.environ, **env, "CARCARE_PORT": str(self.port), "PYTHONDONTWRITEBYTECODE": "1"}
        self.process = None

    def __enter__(self):
        with ExitStack() as resources:
            log = resources.enter_context(tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace"))
            self.process = subprocess.Popen([sys.executable, "-u", str(APP)], env=self.env, cwd=ROOT,
                                            stdout=log, stderr=subprocess.STDOUT)
            resources.callback(self._stop)
            deadline = time.monotonic() + STARTUP_TIMEOUT
            last_error = "No readiness response received."
            while (remaining := deadline - time.monotonic()) > 0:
                if self.process.poll() is not None:
                    break
                try:
                    status, _ = self.call("GET", "/api/vehicles", timeout=min(2, remaining))
                    if status == 200:
                        self._resources = resources.pop_all()
                        return self
                    last_error = f"GET /api/vehicles returned HTTP {status}."
                except (OSError, HTTPException, ValueError) as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(min(0.2, max(0, deadline - time.monotonic())))

            code = self.process.poll()
            reason = (f"The application did not start within {STARTUP_TIMEOUT} seconds." if code is None
                      else f"The application exited with status {code}.")
            self._stop()
            log.seek(0)
            raise SystemExit(f"{reason}\nLast readiness check: {last_error}\n"
                             f"Application log:\n{log.read().strip() or '(empty)'}")

    def _stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def __exit__(self, *_):
        self._resources.close()

    def call(self, method, path, payload=None, timeout=180):
        with closing(HTTPConnection("127.0.0.1", self.port, timeout=timeout)) as conn:
            body = json.dumps(payload) if payload is not None else None
            conn.request(method, path, body, {"Content-Type": "application/json"} if body else {})
            response = conn.getresponse()
            raw = response.read()
            kind = response.getheader("Content-Type", "")
            return response.status, json.loads(raw) if kind.startswith("application/json") else raw.decode()


def check(condition, label, detail=""):
    if not condition:
        raise SystemExit(f"FAIL  {label}{': ' + str(detail) if detail else ''}")
    print(f"PASS  {label}")


def dashboard(app, car_id):
    status, data = app.call("GET", f"/api/dashboard?vehicle_id={car_id}")
    check(status == 200, "dashboard loads", data)
    return data


def run(real_model):
    receipt = DEMO_RECEIPT.read_text(encoding="utf-8")
    if real_model:
        try:
            facts = runtime_details(PINNED_MODEL)
        except ReceiptRuntimeUnavailable:
            raise SystemExit("Ollama is not reachable on 127.0.0.1:11434, or the model is missing.\n"
                             f"Start Ollama, then run: ollama pull {PINNED_MODEL}")
        print(f"      runtime: Ollama {facts['ollama_version']}, {PINNED_MODEL}, "
              f"{facts['parameter_size']} {facts['quantization_level']}")
        check(facts["weights_digest_matches_pin"], "installed weights match the pinned digest")
    with tempfile.TemporaryDirectory() as folder, (
            stub_runtime() if not real_model else _no_stub()) as runtime_port:
        env = {"CARCARE_DB": str(Path(folder) / "smoke.db"),
               "CARCARE_OLLAMA_MODEL": PINNED_MODEL if real_model else "stub-model"}
        if runtime_port:
            env["CARCARE_OLLAMA_PORT"] = str(runtime_port)
        with App(env) as app:
            status, page = app.call("GET", "/")
            check(status == 200 and "Draft with local AI" in page, "page is served with the receipt draft panel")
            status, demo = app.call("POST", "/api/demo", {})
            check(status == 201, "demo data loads into an empty database", demo)
            car_id = demo["vehicle_id"]
            before = dashboard(app, car_id)
            check((len(before["records"]), before["total_cents"]) == (3, 35999), "demo shows 3 records and $359.99")
            status, assist = app.call("GET", "/api/receipt-assist")
            check(status == 200 and assist["enabled"], "AI drafting is enabled", assist)

            started = time.perf_counter()
            status, draft = app.call("POST", "/api/receipt-draft", {"vehicle_id": car_id, "receipt_text": receipt})
            seconds = time.perf_counter() - started
            check(status == 200 and draft["status"] == "needs_review", f"model draft returned in {seconds:.1f} s", draft)
            check(draft["owner_confirmed"] is False, "draft is not confirmed")
            check(len(dashboard(app, car_id)["records"]) == 3, "draft did not write a record")
            proposal = draft["proposal"]
            flags = {k: v["status"] for k, v in draft["evidence"].items()}
            print("      draft:", json.dumps(proposal))
            print("      flags:", json.dumps(flags))
            if not real_model:
                check(proposal == {"service_date": "2026-11-16", "service_item": "Oil change",
                                   "category": "Maintenance", "mileage": 52000, "cost": "89.99",
                                   "provider": "QuickLube Express"}, "miles converted to 52,000 km; total $89.99")
            missing = [k for k, v in proposal.items() if v is None and k != "provider"]
            check(not missing, "draft has every required field", missing)

            record = {**proposal, "vehicle_id": car_id, "owner_confirmed": True, "operation_id": str(uuid4()),
                      "notes": "Smoke test: drafted from receipt text, confirmed by owner."}
            status, saved = app.call("POST", "/api/records", record)
            check(status == 201, "owner Confirm & save writes the record", saved)
            after = dashboard(app, car_id)
            cents = round(float(proposal["cost"]) * 100)
            check((len(after["records"]), after["total_cents"]) == (4, 35999 + cents),
                  f"dashboard shows 4 records and ${(35999 + cents) / 100:.2f}")
            status, again = app.call("POST", "/api/records", record)
            check(status == 201 and again["id"] == saved["id"], "repeated submit does not duplicate the record")

        with App(env) as app:
            check(dashboard(app, car_id)["total_cents"] == 35999 + cents, "record persists after a restart")

        env["CARCARE_OLLAMA_PORT"] = str(free_port())
        env["CARCARE_OLLAMA_TIMEOUT"] = "3"
        with App(env) as app:
            status, failed = app.call("POST", "/api/receipt-draft", {"vehicle_id": car_id, "receipt_text": receipt})
            check(status == 503 and failed["reason"] == "runtime_unavailable", "R2: runtime down returns 503", failed)
            manual = {"vehicle_id": car_id, "service_date": proposal["service_date"], "service_item": "Inspection",
                      "category": "Maintenance", "mileage": 52010, "cost": "21.00", "provider": "Manual entry",
                      "owner_confirmed": True, "operation_id": str(uuid4())}
            status, _ = app.call("POST", "/api/records", manual)
            check(status == 201 and len(dashboard(app, car_id)["records"]) == 5, "R2: manual entry still saves")
    print("Smoke test passed" + (f" with {PINNED_MODEL}." if real_model else " with the stub runtime."))


@contextmanager
def _no_stub():
    yield None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CarCareLog end-to-end smoke test")
    parser.add_argument("--real-model", action="store_true",
                        help=f"use {PINNED_MODEL} in Ollama on 127.0.0.1:11434 instead of the stub")
    run(parser.parse_args().real_model)
