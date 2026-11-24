"""Exercise account isolation over the same HTTP entry point used by the browser."""
import json
import re
import sqlite3
import threading
import time
import unittest
from contextlib import closing
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory

from backend import owner_site


class OwnerSiteTest(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        self.server = owner_site.make_server(0, self.folder)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.03}, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.origin = self.server.site.origin
        self.password = "test-only passphrase"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, cookie=None, origin=None, workspace=None):
        headers = {"Content-Type": "application/json", "Origin": origin or self.origin}
        if cookie:
            headers["Cookie"] = cookie
        if workspace:
            headers["X-CarCare-Workspace"] = workspace
        with closing(HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)) as conn:
            conn.request(method, path, json.dumps(body).encode() if body is not None else None, headers=headers)
            resp = conn.getresponse()
            output = resp.read().decode("utf-8-sig")
            return resp.status, json.loads(output) if "application/json" in resp.getheader("Content-Type") else output, dict(resp.getheaders())

    def register(self, username):
        status, _, headers = self.request("POST", "/api/auth/register", {"username": username, "password": self.password})
        self.assertEqual(status, 201)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Strict", headers["Set-Cookie"])
        return headers["Set-Cookie"].split(";")[0]

    def test_signed_out_routes_and_browser_entry(self):
        self.assertIn("Create a local account", self.request("GET", "/")[1])
        self.assertEqual(self.request("GET", "/health")[:2], (200, {"status":"ok"}))
        for method, path in [("GET", "/api/vehicles"), ("GET", "/api/dashboard?vehicle_id=1"),
                             ("GET", "/api/answer?vehicle_id=1&question=oil"), ("GET", "/api/export?vehicle_id=1"),
                             ("POST", "/api/records"), ("PUT", "/api/vehicles/1"), ("DELETE", "/api/records/1"),
                             ("POST", "/api/demo"), ("GET", "/api/receipt-assist"), ("POST", "/api/receipt-draft")]:
            with self.subTest(path=path):
                self.assertEqual(self.request(method, path)[0], 401)
        self.assertEqual(self.request("POST", "/internal/v1/prepare-information", {})[0], 404)
        self.assertEqual(self.request("POST", "/api/auth/register", {}, origin="https://other.example")[0], 403)

    def test_accounts_cannot_read_or_change_each_others_records(self):
        a, b = self.register("owner-one"), self.register("owner-two")
        self.assertEqual(self.request("POST", "/api/demo", {}, a)[0], 201)
        self.assertEqual(self.request("GET", "/api/vehicles", cookie=b)[:2], (200, []))
        for path in ("/api/dashboard?vehicle_id=1", "/api/answer?vehicle_id=1&question=oil", "/api/export?vehicle_id=1"):
            self.assertEqual(self.request("GET", path, cookie=b)[0], 404)
        self.assertEqual(self.request("PUT", "/api/vehicles/1", {"name":"Changed","mileage":99999}, b)[0], 404)
        self.assertEqual(self.request("DELETE", "/api/records/1", cookie=b)[0], 404)
        self.assertEqual(self.request("DELETE", "/api/reminders/1", cookie=b)[0], 404)
        original = self.request("GET", "/api/dashboard?vehicle_id=1", cookie=a)[1]
        self.assertEqual(original["total_cents"], 35999)
        self.assertEqual(len(original["records"]), 3)
        status, car, _ = self.request("POST", "/api/vehicles", {"name":"Second owner's car","mileage":123}, b)
        self.assertEqual(status, 201)
        self.assertEqual(car["id"], 1)
        self.assertEqual(self.request("GET", "/api/dashboard?vehicle_id=1", cookie=b)[1]["records"], [])
        self.assertNotIn("Demo garage", self.request("GET", "/api/export?vehicle_id=1", cookie=b)[1])
        self.assertNotIn("Second owner", str(self.request("GET", "/api/vehicles", cookie=a)[1]))
        self.assertEqual(self.request("POST", "/api/demo", {}, b, origin="https://other.example")[0], 403)

    def test_calendar_download_is_scoped_to_signed_in_ledger(self):
        a, b = self.register("calendar-a"), self.register("calendar-b")
        self.request("POST", "/api/demo", {}, cookie=a)
        dashboard = self.request("GET", "/api/dashboard?vehicle_id=1", cookie=a)[1]
        rule = next(r for r in dashboard["reminders"] if r["service_item"] == "Tire rotation")
        path = f'/api/reminders/{rule["id"]}/calendar.ics'
        status, event, headers = self.request("GET", path, cookie=a)
        self.assertEqual(status, 200)
        self.assertIn("text/calendar", headers["Content-Type"])
        self.assertIn(".ics", headers["Content-Disposition"])
        self.assertIn("BEGIN:VALARM", event)
        self.assertEqual(self.request("GET", path, cookie=b)[0], 404)
        self.assertEqual(self.request("GET", path)[0], 401)
        self.assertEqual(self.request("GET", "/api/reminders/bad/calendar.ics", cookie=a)[0], 404)
        self.assertEqual(self.request("GET", "/api/reminders/999999999999999999999/calendar.ics", cookie=a)[0], 404)

    def test_login_logout_rotation_and_expiration(self):
        a = self.register("Returning.Owner")
        self.assertIn('id="sign-out"', self.request("GET", "/", cookie=a)[1])
        self.assertEqual(self.request("GET", "/api/auth/session", cookie=a)[1], {"username":"returning.owner"})
        status, _, _ = self.request("POST", "/api/auth/login", {"username":"returning.owner","password":"incorrect"})
        self.assertEqual(status, 401)
        status, _, response_headers = self.request("POST", "/api/auth/login",
                         {"username":"returning.owner","password":self.password}, a)
        self.assertEqual(status, 200)
        rotated = response_headers["Set-Cookie"].split(";")[0]
        self.assertNotEqual(rotated, a)
        self.assertEqual(self.request("GET", "/api/vehicles", cookie=a)[0], 401)
        self.assertEqual(self.request("POST", "/api/auth/logout", cookie=rotated)[0], 200)
        self.assertEqual(self.request("GET", "/api/vehicles", cookie=rotated)[0], 401)
        _, _, headers = self.request("POST", "/api/auth/login", {"username":"returning.owner","password":self.password})
        with closing(self.server.site.db()) as db, db:
            db.execute("UPDATE sessions SET expires=?", (int(time.time()) - 1,))
            stored = db.execute("SELECT salt,password FROM owners").fetchone()
            self.assertEqual((len(stored[0]),len(stored[1])), (16,32))
        self.assertEqual(self.request("GET", "/api/vehicles", cookie=headers["Set-Cookie"].split(";")[0])[0], 401)

    def test_stale_tab_cannot_write_after_switching_accounts(self):
        a, b = self.register("old-tab"), self.register("new-tab")
        html = self.request("GET", "/", cookie=a)[1]
        old_id = re.search(r'name="carcare-workspace" content="([a-f0-9]{32})"', html).group(1)
        self.assertEqual(self.request("POST", "/api/demo", {}, cookie=b, workspace=old_id)[0], 409)
        self.assertEqual(self.request("GET", "/api/vehicles", cookie=b)[1], [])

    def test_signup_validation_and_separate_new_ledger(self):
        legacy = self.folder / "old-single-owner.sqlite3"
        with closing(sqlite3.connect(legacy)) as db, db:
            db.execute("CREATE TABLE secret(x)")
            db.execute("INSERT INTO secret VALUES('previous private records')")
        original = legacy.read_bytes()
        self.assertEqual(self.request("POST", "/api/auth/register", {"username":"one","password":"short"})[0], 400)
        self.assertEqual(self.request("POST", "/api/auth/register", {"username":"../other","password":self.password})[0], 400)
        owner = self.register("new-user")
        self.assertEqual(self.request("GET", "/api/vehicles", cookie=owner)[1], [])
        self.assertEqual(self.request("POST", "/api/auth/register", {"username":"NEW-USER","password":self.password})[0], 409)
        self.assertEqual(original, legacy.read_bytes())

    def test_account_attempt_budget(self):
        for _ in range(10):
            self.assertTrue(self.server.site.allow_attempt("same device", "demo"))
        self.assertFalse(self.server.site.allow_attempt("same device", "demo"))
