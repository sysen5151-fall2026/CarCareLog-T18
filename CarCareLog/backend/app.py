"""CarCareLog local prototype. Run with: python3 backend/app.py"""

import csv
import io
import json
import os
import re
import sqlite3
import traceback
from contextlib import closing, contextmanager
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import perf_counter
from urllib.parse import parse_qs, urlsplit

if __package__:
    from .function_f22 import (add_months, validate_and_route_owner_request,
        coordinate_confirmed_record_transaction, calculate_maintenance_summary_and_reminders,
        coordinate_ai_requests_and_responses, OperationConflict, OperationGone)
else:
    from function_f22 import (add_months, validate_and_route_owner_request,
        coordinate_confirmed_record_transaction, calculate_maintenance_summary_and_reminders,
        coordinate_ai_requests_and_responses, OperationConflict, OperationGone)

LOCAL_POLICY = {"mode": "local_demo", "require_confirmation": True}

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.environ.get("CARCARE_DB", ROOT / "data" / "carcare.db"))
SERVICES = ["Oil change", "Tire rotation", "Brake service", "Inspection", "Battery", "Other"]


def connect():
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db, db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL, mileage INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            service_date TEXT NOT NULL, service_item TEXT NOT NULL,
            category TEXT NOT NULL, mileage INTEGER NOT NULL, cost_cents INTEGER NOT NULL,
            provider TEXT NOT NULL, notes TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            service_item TEXT NOT NULL, interval_km INTEGER NOT NULL,
            interval_months INTEGER NOT NULL, reference TEXT NOT NULL,
            UNIQUE(vehicle_id, service_item)
        );
        CREATE TABLE IF NOT EXISTS record_operations (
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            operation_id TEXT NOT NULL, fingerprint TEXT NOT NULL, record_id INTEGER NOT NULL,
            deleted INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (vehicle_id, operation_id)
        );
        """)


def text_field(body, key, required=True, limit=1000):
    value = body.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text.")
    value = value.strip()
    if (required and not value) or len(value) > limit:
        raise ValueError(f"Please provide {key} (maximum {limit} characters).")
    return value


def integer(body, key, minimum=0, maximum=10_000_000):
    value = body.get(key)
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value)):
        raise ValueError(f"{key} must be a whole number.")
    value = int(value)
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}.")
    return value


def record_fields(body):
    day = text_field(body, "service_date", limit=10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) or date.fromisoformat(day) > date.today():
        raise ValueError("Service date must be a valid date on or before today.")
    service = text_field(body, "service_item", limit=60)
    category = text_field(body, "category", limit=20)
    if service not in SERVICES or category not in ("Maintenance", "Repair"):
        raise ValueError("Select a supported service item and category.")
    try:
        amount = Decimal(str(body.get("cost", "")))
        if not amount.is_finite() or not 0 <= amount <= 1_000_000 or amount != amount.quantize(Decimal("0.01")):
            raise ValueError("Cost must be nonnegative with at most two decimal places.")
    except InvalidOperation as exc:
        raise ValueError("Enter a valid cost.") from exc
    return (day, service, category, integer(body, "mileage"), int(amount * 100),
            text_field(body, "provider", required=False, limit=120),
            text_field(body, "notes", required=False, limit=2000))


def vehicle(db, vehicle_id):
    row = db.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
    if row is None:
        raise LookupError("Vehicle not found.")
    return dict(row)


def all_records(db, vehicle_id):
    return [dict(r) for r in db.execute(
        "SELECT * FROM records WHERE vehicle_id=? ORDER BY service_date DESC, mileage DESC, id DESC",
        (vehicle_id,))]


def dashboard_inputs(db, vehicle_id):
    car = vehicle(db, vehicle_id)
    records = all_records(db, vehicle_id)
    rules = [dict(r) for r in db.execute(
        "SELECT * FROM reminders WHERE vehicle_id=? ORDER BY service_item", (vehicle_id,))]
    return car, records, rules


def dashboard(db, vehicle_id):
    """F.2.2.4 adapter: query C.3 and calculate prepared vehicle information."""
    car, records, rules = dashboard_inputs(db, vehicle_id)
    return calculate_maintenance_summary_and_reminders(records, rules,
        vehicle_context=car, as_of=date.today())


def csv_export(records):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Record ID", "Date", "Service", "Category", "Mileage (km)", "Cost (USD)", "Provider", "Notes"])
    for r in records:
        cells = [r["id"], r["service_date"], r["service_item"], r["category"], r["mileage"],
                 f'{r["cost_cents"] / 100:.2f}', r["provider"], r["notes"]]
        writer.writerow(["'" + c if isinstance(c, str) and c.lstrip().startswith(("=", "+", "-", "@")) else c for c in cells])
    return output.getvalue().encode("utf-8-sig")


def seed_demo(db):
    if db.execute("SELECT count(*) FROM vehicles").fetchone()[0]:
        raise ValueError("Demo data can only be loaded into an empty database.")
    car_id = db.execute("INSERT INTO vehicles(name,mileage) VALUES(?,?)", ("Demo · 2020 Toyota Corolla", 52000)).lastrowid
    for days, service, category, mileage, cents, provider in [
        (210, "Oil change", "Maintenance", 44000, 7999, "Demo service center"),
        (150, "Tire rotation", "Maintenance", 48000, 3500, "Demo tire shop"),
        (20, "Brake service", "Repair", 51500, 24500, "Demo garage")]:
        db.execute("INSERT INTO records(vehicle_id,service_date,service_item,category,mileage,cost_cents,provider,notes) VALUES(?,?,?,?,?,?,?,?)",
                   (car_id, (date.today()-timedelta(days=days)).isoformat(), service, category, mileage, cents, provider, "Sample record for classroom demonstration."))
    for service, km, months in [("Oil change", 8000, 6), ("Tire rotation", 5000, 6)]:
        db.execute("INSERT INTO reminders(vehicle_id,service_item,interval_km,interval_months,reference) VALUES(?,?,?,?,?)",
                   (car_id, service, km, months, "Demo interval only. Replace with your vehicle manual reference."))
    return car_id


class Handler(BaseHTTPRequestHandler):
    @contextmanager
    def measure(self, stage):
        start = perf_counter()
        try:
            yield
        finally:
            self.timings[stage] = (perf_counter() - start) * 1000

    def measured_dashboard(self, db, car_id):
        with self.measure("store_dashboard"):
            car, records, rules = dashboard_inputs(db, car_id)
        with self.measure("app_summary"):
            return calculate_maintenance_summary_and_reminders(records, rules,
                vehicle_context=car, as_of=date.today())

    def reply(self, payload, status=200, content_type="application/json; charset=utf-8", filename=None):
        with self.measure("app_response_encode"):
            data = json.dumps(payload, ensure_ascii=False).encode() if isinstance(payload, (dict, list)) else payload
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        if self.headers.get("X-CarCare-Timing") == "1":
            self.send_header("Server-Timing", ", ".join(
                f"{stage};dur={elapsed:.4f}" for stage, elapsed in self.timings.items()))
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 50_000:
            raise ValueError("Request body must be between 1 and 50,000 bytes.")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("Send JSON data.")
        body = json.loads(self.rfile.read(size))
        if not isinstance(body, dict):
            raise ValueError("Request body must be a JSON object.")
        return body

    def dispatch(self):
        # The demo is local-only. Reject remote Host/Origin values and avoid exposing the DB.
        host = self.headers.get("Host", "")
        expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if host not in expected or self.headers.get("Origin", "http://" + host) != "http://" + host:
            return self.reply({"error": "Use the local app address."}, 403)
        parts = urlsplit(self.path)
        path = parts.path
        query = parse_qs(parts.query)
        if self.command == "GET" and path in ("/", "/app.js", "/styles.css"):
            file_name = "index.html" if path == "/" else path[1:]
            media = {"index.html": "text/html", "app.js": "text/javascript", "styles.css": "text/css"}[file_name]
            return self.reply((ROOT / "frontend" / file_name).read_bytes(), content_type=media + "; charset=utf-8")
        body = self.body() if self.command in ("POST", "PUT") else {}
        with closing(connect()) as db, db:
            # Thin localhost-only contract adapters. They reuse the same model
            # functions as the product; none establish owner authentication.
            if path.startswith('/internal/v1/') and self.command == 'POST':
                if path == '/internal/v1/validate-and-route':
                    request = validate_and_route_owner_request(body,
                        owner_authorization_and_confirmation_policy=LOCAL_POLICY,
                        configuration_and_maintenance_instructions={'operations': ['create_record']},
                        record_store=db, field_validator=record_fields)
                    keys = ['service_date', 'service_item', 'category', 'mileage', 'cost_cents', 'provider', 'notes']
                    record = dict(zip(keys, request['fields']))
                    record['cost'] = f"{record.pop('cost_cents') / 100:.2f}"
                    return self.reply({'operation':request['operation'], 'vehicle_id':request['vehicle_id'],
                        'owner_confirmed':request['owner_confirmed'], 'record':record})
                if path == '/internal/v1/confirmed-transaction':
                    if not isinstance(body.get('record'), dict):
                        raise ValueError('A routed record object is required.')
                    raw = {**body['record'], 'vehicle_id':body.get('vehicle_id'),
                           'operation':body.get('operation'), 'owner_confirmed':body.get('owner_confirmed')}
                    # Revalidate a caller-supplied DTO before the persistence boundary.
                    request = validate_and_route_owner_request(raw,
                        owner_authorization_and_confirmation_policy=LOCAL_POLICY,
                        configuration_and_maintenance_instructions={'operations':['create_record']},
                        record_store=db, field_validator=record_fields)
                    return self.reply(coordinate_confirmed_record_transaction(request,
                        owner_authorization_and_confirmation_policy=LOCAL_POLICY, record_store=db), 201)
                if path == '/internal/v1/prepare-information':
                    return self.reply(dashboard(db, integer(body,'vehicle_id',minimum=1)))
                if path == '/internal/v1/coordinate-ai':
                    car_id = integer(body, 'vehicle_id', minimum=1)
                    vehicle(db,car_id)
                    if body.get('kind') not in ('receipt','question'):
                        raise ValueError('AI request kind must be receipt or question.')
                    try:
                        coordinate_ai_requests_and_responses(body,
                            configured_ai_service_contract_limits={'enabled':False},
                            authorized_records_and_source_references=all_records(db,car_id))
                    except NotImplementedError:
                        return self.reply({'status':'unavailable', 'vehicle_id':car_id,
                            'proposal':None, 'message':'External AI is not implemented; use manual entry.'},503)
                    raise RuntimeError('An unreviewed AI implementation returned unexpectedly.')
            if path == "/api/vehicles":
                if self.command == "GET":
                    with self.measure("store_vehicle_list"):
                        vehicles = [dict(r) for r in db.execute("SELECT * FROM vehicles ORDER BY id")]
                    return self.reply(vehicles)
                if self.command == "POST":
                    car_id = db.execute("INSERT INTO vehicles(name,mileage) VALUES(?,?)",
                                        (text_field(body, "name", limit=120), integer(body, "mileage"))).lastrowid
                    db.commit()
                    return self.reply(vehicle(db, car_id), 201)
            if path == "/api/demo" and self.command == "POST":
                car_id = seed_demo(db)
                db.commit()
                return self.reply({"vehicle_id": car_id}, 201)
            match = re.fullmatch(r"/api/vehicles/(\d+)", path)
            if match and self.command == "PUT":
                car_id = int(match[1])
                vehicle(db, car_id)
                mileage = integer(body, "mileage")
                highest = db.execute("SELECT coalesce(max(mileage),0) FROM records WHERE vehicle_id=?", (car_id,)).fetchone()[0]
                if mileage < highest:
                    raise ValueError("Current mileage cannot be below a recorded service mileage.")
                db.execute("UPDATE vehicles SET name=?,mileage=? WHERE id=?", (text_field(body, "name", limit=120), mileage, car_id))
                db.commit()
                return self.reply(vehicle(db, car_id))
            if path in ("/api/dashboard", "/api/export", "/api/answer") and self.command == "GET":
                car_id = integer({"vehicle_id": query.get("vehicle_id", [""])[0]}, "vehicle_id", minimum=1)
                if path == "/api/dashboard":
                    return self.reply(self.measured_dashboard(db, car_id))
                data = dashboard(db, car_id)
                if path == "/api/export":
                    return self.reply(csv_export(data["records"]), content_type="text/csv; charset=utf-8", filename=f"carcarelog-{car_id}.csv")
                question = query.get("question", [""])[0]
                records = data["records"]
                if question == "total":
                    answer = f'Total recorded spending: ${data["total_cents"] / 100:.2f} across {len(records)} records.'
                    sources = [r["id"] for r in records]
                elif question == "oil":
                    oil = next((r for r in records if r["service_item"] == "Oil change"), None)
                    answer = f'Last recorded oil change: {oil["service_date"]}, at {oil["mileage"]:,} km.' if oil else "Insufficient evidence: no oil-change record is available."
                    sources = [oil["id"]] if oil else []
                else:
                    raise ValueError("Choose a supported history question.")
                return self.reply({"answer": answer, "record_ids": sources, "method": "Recorded-data lookup"})
            if path == "/api/records" and self.command == "POST":
                with self.measure("app_validate_and_route"):
                    request = validate_and_route_owner_request(body,
                        owner_authorization_and_confirmation_policy=LOCAL_POLICY,
                        configuration_and_maintenance_instructions={"operations": ["create_record"]},
                        record_store=db, field_validator=record_fields)
                with self.measure("store_confirmed_transaction"):
                    result = coordinate_confirmed_record_transaction(request,
                        owner_authorization_and_confirmation_policy=LOCAL_POLICY, record_store=db)
                if query.get("include") == ["dashboard"]:
                    try:
                        result["dashboard"] = self.measured_dashboard(db, request["vehicle_id"])
                    except sqlite3.Error:
                        # The write already committed. A failed read cannot turn it into a failed save.
                        result["dashboard_unavailable"] = True
                return self.reply(result, 201)
            match = re.fullmatch(r"/api/records/(\d+)", path)
            if match and self.command in ("PUT", "DELETE"):
                rec_id = int(match[1])
                if self.command == "DELETE":
                    db.execute("BEGIN IMMEDIATE")
                row = db.execute("SELECT * FROM records WHERE id=?", (rec_id,)).fetchone()
                if row is None:
                    raise LookupError("Record not found.")
                if self.command == "DELETE":
                    db.execute("UPDATE record_operations SET deleted=1 WHERE vehicle_id=? AND record_id=?",
                               (row["vehicle_id"], rec_id))
                    db.execute("DELETE FROM records WHERE id=?", (rec_id,))
                else:
                    if body.get("owner_confirmed") is not True:
                        raise ValueError("Explicit confirmation is required before updating a record.")
                    fields = record_fields(body)
                    db.execute("UPDATE records SET service_date=?,service_item=?,category=?,mileage=?,cost_cents=?,provider=?,notes=? WHERE id=?", (*fields, rec_id))
                    db.execute("UPDATE vehicles SET mileage=max(mileage,?) WHERE id=?", (fields[3], row["vehicle_id"]))
                db.commit()
                return self.reply({"ok": True})
            if path == "/api/reminders" and self.command == "POST":
                car_id = integer(body, "vehicle_id", minimum=1)
                vehicle(db, car_id)
                service = text_field(body, "service_item", limit=60)
                km = integer(body, "interval_km", maximum=1_000_000)
                months = integer(body, "interval_months", maximum=120)
                if service not in SERVICES or not (km or months):
                    raise ValueError("Select a service and enter at least one nonzero interval.")
                db.execute("INSERT INTO reminders(vehicle_id,service_item,interval_km,interval_months,reference) VALUES(?,?,?,?,?) ON CONFLICT(vehicle_id,service_item) DO UPDATE SET interval_km=excluded.interval_km,interval_months=excluded.interval_months,reference=excluded.reference",
                           (car_id, service, km, months, text_field(body, "reference", limit=300)))
                db.commit()
                return self.reply({"ok": True})
            match = re.fullmatch(r"/api/reminders/(\d+)", path)
            if match and self.command == "DELETE":
                cursor = db.execute("DELETE FROM reminders WHERE id=?", (int(match[1]),))
                if cursor.rowcount == 0:
                    raise LookupError("Reminder not found.")
                db.commit()
                return self.reply({"ok": True})
        self.reply({"error": "Route not found."}, 404)

    def handle_request(self):
        self.timings = {}
        try:
            self.dispatch()
        except OperationConflict as exc:
            self.reply({"error": str(exc)}, 409)
        except OperationGone as exc:
            self.reply({"error": str(exc)}, 410)
        except (ValueError, InvalidOperation) as exc:
            self.reply({"error": str(exc)}, 400)
        except LookupError as exc:
            self.reply({"error": str(exc)}, 404)
        except Exception:
            traceback.print_exc()
            self.reply({"error": "Server error. Check the application terminal."}, 500)

    do_GET = do_POST = do_PUT = do_DELETE = handle_request


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("CARCARE_PORT", "8000"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"CarCareLog is running at http://127.0.0.1:{port}", flush=True)
    print(f"Press Ctrl+C to stop. Your records are saved in {DB_PATH}.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
