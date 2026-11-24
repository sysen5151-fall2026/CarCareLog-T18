"""Separate account-based classroom entry point for CarCareLog."""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import closing
from http.cookies import CookieError, SimpleCookie
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

if __package__:
    from . import app
else:
    import app


SESSION_SECONDS = 8 * 3600
USERNAME = re.compile(r"[a-z0-9][a-z0-9_.-]{2,31}")
DUMMY_SALT = b"CarCareLog-salt!"
PASSWORD_ROUNDS = 600_000


def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ROUNDS)


class Site:
    def __init__(self, folder, origin):
        parsed = urlsplit(origin)
        local = parsed.hostname in {"localhost", "127.0.0.1"}
        if (parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or not parsed.netloc
                or parsed.scheme != "http" or not local):
            raise ValueError("The account demo requires a local HTTP loopback address.")
        self.origin = f"{parsed.scheme}://{parsed.netloc}"
        self.authority = parsed.netloc
        # Browser cookies are host scoped, not port scoped. Keep simultaneous demo instances independent.
        self.cookie_name = f"carcare_demo_{parsed.port or 80}"
        self.folder = Path(folder)
        self.ledgers = self.folder / "ledgers"
        self.ledgers.mkdir(parents=True, exist_ok=True)
        self.database = self.folder / "accounts.sqlite3"
        self.lock = threading.Lock()
        self.initialized_ledgers = set()
        self.attempts = defaultdict(deque)
        self.capacity = threading.BoundedSemaphore(2)
        self.inference = threading.BoundedSemaphore(1)
        with closing(self.db()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS owners (
                    id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
                    salt BLOB NOT NULL, password BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash BLOB PRIMARY KEY,
                    owner_id TEXT NOT NULL REFERENCES owners(id) ON DELETE CASCADE,
                    expires INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires);
            """)

    def db(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def ledger(self, owner_id):
        return self.ledgers / (owner_id + ".sqlite3")

    def initialize_ledger(self, owner_id):
        # Existing owners can arrive with a session created by an earlier release.
        with self.lock:
            if owner_id not in self.initialized_ledgers:
                app.init_db(self.ledger(owner_id))
                self.initialized_ledgers.add(owner_id)

    def allow_attempt(self, peer, username):
        now = time.monotonic()
        with self.lock:
            for key, times in list(self.attempts.items()):
                while times and times[0] <= now - 60:
                    times.popleft()
                if not times:
                    del self.attempts[key]
            keys = ((("site", ""), 120), (("peer", peer), 60), (("user", username), 10))
            if any(len(self.attempts.get(key, ())) >= limit for key, limit in keys):
                return False
            for key, _ in keys:
                self.attempts[key].append(now)
            return True

    def account(self, username, password, register):
        with closing(self.db()) as db, db:
            if register:
                owner_id = secrets.token_hex(16)
                salt = secrets.token_bytes(16)
                digest = password_digest(password, salt)
                try:
                    db.execute("INSERT INTO owners VALUES(?,?,?,?)", (owner_id, username, salt, digest))
                except sqlite3.IntegrityError:
                    return None
                self.initialize_ledger(owner_id)
            else:
                row = db.execute("SELECT id,salt,password FROM owners WHERE username=?", (username,)).fetchone()
                candidate = password_digest(password, row[1] if row else DUMMY_SALT)
                if not row or not hmac.compare_digest(candidate, row[2]):
                    return None
                owner_id = row[0]
            db.execute("DELETE FROM sessions WHERE expires<=?", (int(time.time()),))
            token = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions VALUES(?,?,?)",
                       (hashlib.sha256(token.encode()).digest(), owner_id, int(time.time()) + SESSION_SECONDS))
            return token

    def session(self, digest):
        if digest is None:
            return None
        with closing(self.db()) as db:
            return db.execute("""SELECT o.id, o.username FROM sessions s JOIN owners o ON o.id=s.owner_id
                                 WHERE s.token_hash=? AND s.expires>?""", (digest, int(time.time()))).fetchone()

    def revoke(self, digest):
        if digest:
            with closing(self.db()) as db, db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))


class AccountHandler(app.Handler):
    server_version = "CarCareLog"
    sys_version = ""

    @property
    def site(self):
        return self.server.site

    def allowed_origin(self):
        supplied = self.headers.get("Origin")
        write = self.command not in ("GET", "HEAD")
        return (self.headers.get("Host") == self.site.authority
                and (supplied == self.site.origin or (not write and supplied is None)))

    def end_headers(self):
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                         "img-src 'self' blob: data:; frame-ancestors 'none'; object-src 'none'; base-uri 'none'")
        if getattr(self, "_cookie", None):
            self.send_header("Set-Cookie", self._cookie)
        super().end_headers()

    def cookie_digest(self):
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            item = cookies.get(self.site.cookie_name)
            if item and re.fullmatch(r"[A-Za-z0-9_-]{43}", item.value):
                return hashlib.sha256(item.value.encode()).digest()
        except CookieError:
            pass
        return None

    def set_session_cookie(self, value, lifetime):
        self._cookie = f"{self.site.cookie_name}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age={lifetime}"

    def open_ledger(self):
        self.site.initialize_ledger(self.owner[0])
        return app.connect(self.site.ledger(self.owner[0]))

    def auth(self, path):
        form = self.body(2048)
        username, password = form.get("username"), form.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            return self.reply({"error": "Enter a demo username and password."}, 400)
        username = username.strip().lower()
        if not USERNAME.fullmatch(username) or not (1 <= len(password) <= 128):
            return self.reply({"error": "Use a 3–32 character username and a password of up to 128 characters."}, 400)
        if not self.site.allow_attempt(self.client_address[0], username) or not self.site.capacity.acquire(blocking=False):
            return self.reply({"error": "Too many requests. Please try again in a minute."}, 429)
        try:
            register = path == "/api/auth/register"
            if register and len(password) < 12:
                return self.reply({"error": "Choose a demo password with at least 12 characters."}, 400)
            token = self.site.account(username, password, register)
        finally:
            self.site.capacity.release()
        if not token:
            if register:
                return self.reply({"error": "That username is unavailable. Choose another."}, 409)
            return self.reply({"error": "The username or password did not match."}, 401)
        self.site.revoke(self.cookie_digest())
        self.set_session_cookie(token, SESSION_SECONDS)
        return self.reply({"username": username}, 201 if register else 200)

    def dispatch(self):
        if not self.allowed_origin():
            return self.reply({"error": "Use the configured site address."}, 403)
        path = urlsplit(self.path).path
        if self.command == "GET" and path == "/health":
            return self.reply({"status": "ok"})
        if self.command == "GET" and path in {"/styles.css", "/app.js", "/account.js", "/signin.js", "/manual.js", "/questions.js"}:
            media = "text/css" if path == "/styles.css" else "text/javascript"
            return self.reply((app.ROOT / "frontend" / path[1:]).read_bytes(), content_type=media + "; charset=utf-8")
        if self.command == "POST" and path in {"/api/auth/login", "/api/auth/register"}:
            return self.auth(path)
        self.owner = self.site.session(self.cookie_digest())
        expected_workspace = self.headers.get("X-CarCare-Workspace")
        if expected_workspace and (not self.owner or expected_workspace != self.owner[0]):
            return self.reply({"code": "workspace_changed", "error": "The signed-in account has changed. Reload the workspace."}, 409)
        if self.command == "POST" and path == "/api/auth/logout":
            self.site.revoke(self.cookie_digest())
            self.set_session_cookie("", 0)
            return self.reply({"signed_out": True})
        if path.startswith("/internal/"):
            return self.reply({"error": "Not found."}, 404)
        if self.command == "GET" and path in ("/", "/signin"):
            if not self.owner:
                html = (app.ROOT / "frontend" / "signin.html").read_text(encoding="utf-8")
            else:
                html = (app.ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
                # The workspace id is not a session credential. A stale tab can use it to
                # reject a write when another tab has signed into a different owner.
                html = html.replace("<!-- account-script -->", f'<meta name="carcare-workspace" content="{self.owner[0]}">'
                                    '<script src="/account.js" defer></script>')
                html = html.replace("<!-- account-control -->", '<button id="sign-out" class="secondary">Sign out</button>')
                html = html.replace("Local prototype", "Personal demo workspace")
                html = html.replace("Local classroom prototype", "Team 18 local account demo")
            return self.reply(html.encode(), content_type="text/html; charset=utf-8")
        if not self.owner:
            return self.reply({"error": "Please sign in to your workspace."}, 401)
        if self.command == "GET" and path == "/api/auth/session":
            return self.reply({"username": self.owner[1]})
        if self.command == "POST" and path in ("/api/receipt-draft", "/api/questions"):
            if not self.site.inference.acquire(blocking=False):
                return self.reply({"error": "The local assistant is busy. Try again shortly."}, 429)
            try:
                return super().dispatch()
            finally:
                self.site.inference.release()
        return super().dispatch()


def make_server(port, folder):
    server = ThreadingHTTPServer(("127.0.0.1", port), AccountHandler)
    try:
        server.site = Site(folder, f"http://127.0.0.1:{server.server_port}")
    except BaseException:
        server.server_close()
        raise
    return server


if __name__ == "__main__":
    port = int(os.environ.get("CARCARE_PORT", "8000"))
    folder = os.environ.get("CARCARE_SITE_DIR", Path.home() / ".carcarelog-site")
    with app.RecoveryManager.for_accounts(folder) as recovery:
        with make_server(port, folder) as service:
            recovery.start()
            print(f"CarCareLog account site: {service.site.origin}", flush=True)
            service.serve_forever()
