"""Vehicle-scoped maintenance manual sources, quoted intervals and owner approval."""
import base64
import hashlib
import io
import json
import re
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_REQUEST_BYTES = ((MAX_FILE_BYTES + 2) // 3) * 4 + 2048
MAX_TEXT = 2_000_000
PUBLISHERS = {
    "assets.sia.toyota.com": "/publications/",
    "techinfo.honda.com": "/rjanisis/pubs/",
    "www.tesla.com": "/ownersmanual/",
    "service.tesla.com": "/docs/",
}


def init_schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS manuals (
        id INTEGER PRIMARY KEY, vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
        title TEXT NOT NULL, sha256 TEXT NOT NULL, source_url TEXT NOT NULL,
        verification TEXT NOT NULL, is_current INTEGER NOT NULL DEFAULT 1,
        candidates TEXT NOT NULL
    )""")
    db.execute("""CREATE UNIQUE INDEX IF NOT EXISTS current_vehicle_manual
                  ON manuals(vehicle_id) WHERE is_current = 1""")
    db.execute("""CREATE TABLE IF NOT EXISTS manual_pages (
        manual_id INTEGER NOT NULL REFERENCES manuals(id), page INTEGER NOT NULL,
        text TEXT NOT NULL, PRIMARY KEY(manual_id, page)
    )""")


def publisher_url(url):
    if not isinstance(url, str) or len(url) > 1600 or not url.isascii():
        raise ValueError("Enter a direct HTTPS link on a supported manufacturer's manual site.")
    parsed = urlsplit(url)
    prefix = PUBLISHERS.get(parsed.hostname)
    if (not prefix or parsed.scheme != "https" or parsed.username is not None
            or parsed.password is not None or parsed.port not in (None, 443)
            or parsed.fragment or parsed.query or "\\" in url or any(ord(ch) <= 32 or ord(ch) == 127 for ch in url)
            or not parsed.path.lower().startswith(prefix.lower())
            or unquote(parsed.path) != parsed.path or ".." in parsed.path.split("/")):
        raise ValueError("Use a direct manual URL on a supported manufacturer's site without tracking parameters.")
    return url


class PublisherRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, publisher_url(newurl))


def download(url):
    request = Request(publisher_url(url), headers={"User-Agent": "CarCareLog-ManualReader/1"})
    try:
        with build_opener(PublisherRedirects()).open(request, timeout=12) as response:
            final_url = publisher_url(response.geturl())
            content_type = response.headers.get_content_type()
            raw = response.read(MAX_FILE_BYTES + 1)
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError("Could not retrieve the manufacturer page. Import a saved text or PDF copy instead.") from exc
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Choose a manual or section no larger than 16 MiB.")
    return final_url, content_type, raw


class ManualHTML(HTMLParser):
    blocks = {"article", "br", "div", "h1", "h2", "h3", "h4", "li", "p", "section", "tr", "ul"}
    omitted = {"script", "style", "svg", "nav", "header", "footer", "head", "noscript", "template"}

    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.omitted:
            self.hidden_depth += 1
        if not self.hidden_depth and tag in self.blocks:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.omitted and self.hidden_depth:
            self.hidden_depth -= 1
        if not self.hidden_depth and tag in self.blocks:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden_depth:
            # HTML source line wraps within a list item are spaces in the displayed manual.
            self.parts.append(re.sub(r"\s+", " ", data))


def pdf_text(raw):
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ValueError("For PDF import install CarCareLog/requirements-manual-pdf.txt, or paste the manual text.") from exc
    try:
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or len(reader.pages) > 750:
            raise ValueError("Import an unlocked manual of up to 750 pages.")
        for page in reader.pages:
            yield page.extract_text() or ""
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("The PDF could not be read. Import a text-based PDF or paste the relevant section.") from exc


def pages_from(raw, media):
    if raw.startswith(b"%PDF-"):
        pages = pdf_text(raw)
    elif media in ("text/plain", "text/html", "application/xhtml+xml"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("Use a UTF-8 text file or a text-based PDF.") from exc
        if "\0" in text:
            raise ValueError("Use a UTF-8 text file or a text-based PDF.")
        if media != "text/plain":
            parser = ManualHTML()
            parser.feed(text)
            parser.close()
            text = "".join(parser.parts)
        pages = text.split("\f")
    else:
        raise ValueError("Use a text-based PDF, plain text, or a supported manufacturer's manual web page.")
    extracted = []
    size = 0
    for page_no, page in enumerate(pages, 1):
        size += len(page)
        if size > MAX_TEXT or page_no > 750:
            raise ValueError("Import a smaller section (up to 750 pages and 2 million text characters).")
        lines = [" ".join(line.split()) for line in page.splitlines()]
        extracted.append("\n".join(line for line in lines if line))
    if not any(page.strip() for page in extracted):
        raise ValueError("No readable text was found. For a scanned manual, paste the relevant passage.")
    return extracted


SERVICES = {
    "Oil change": r"\b(?:oil changes?|(?:change|replace)(?: the)? (?:engine |motor )?oil)\b",
    "Tire rotation": r"\b(?:tires? rotations?|tyres? rotations?|rotat(?:e|ing)(?: the)? (?:tires|tyres))\b",
    "Brake service": r"\bbrake servic(?:e|ing)\b",
    "Inspection": r"\b(?:vehicle|multi[- ]point|scheduled) inspection\b",
    "Battery": r"\b(?:battery replacement|replace (?:the )?(?:12[- ]volt )?battery)\b",
}
QUANTITY = re.compile(
    r"(?<![\w.,/\-])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*"
    r"(kilometers?|kilometres?|km|miles?|mi|months?|years?)\b", re.I)
SEPARATE_ACTION = re.compile(
    r"(?:[;,]|\b(?:and|or|then|also)\b)\s*(?:(?:also|then)\s+)?"
    r"(?:check|inspect|replace|change|adjust|rotate|flush|clean|test|lubricate|service|verify|reset)\b",
    re.I)


def extract_intervals(pages):
    candidates = []
    for page, text in enumerate(pages, 1):
        text = re.sub(r"\n(?=\(|(?:or|if|unless|whichever|under)\s)", " ", text, flags=re.I)
        for line in re.split(r"\n|(?<=[.!?])\s+(?=[A-Z])", text):
            if len(line) > 620 or not re.search(r"\b(?:every|intervals?|whichever comes first)\b", line, re.I):
                continue
            # Schedule milestones, ranges and multiple operating schedules need interpretation.
            if re.search(r"\b(?:never|not|except|first time|initially)\b|\d\s*[-–]\s*\d|\d\s+to\s+\d", line, re.I):
                continue
            # A quantity beside an unrelated action is not a recurring rule for this service.
            if (len(re.findall(r"\bevery\b", line, re.I)) > 1 or SEPARATE_ACTION.search(line)
                    or re.search(r"\b(?:as needed|as required|on condition)\b", line, re.I)):
                continue
            services = [label for label, pattern in SERVICES.items() if re.search(pattern, line, re.I)]
            if len(services) != 1:
                continue
            values = {"km": set(), "mi": set(), "months": set()}
            quantities = QUANTITY.findall(line.lower())
            if any(len(number.replace(",", "")) > 10 for number, _ in quantities):
                continue
            for number, unit in quantities:
                value = float(number.replace(",", ""))
                key = "months" if unit.startswith(("month", "year")) else ("mi" if unit.startswith("mi") else "km")
                values[key].add(value * 12 if unit.startswith("year") else value)
            if any(len(entries) > 1 for entries in values.values()):
                continue
            km, mi, months = [next(iter(entries), 0) for entries in values.values()]
            if km and mi and abs(km - mi * 1.609344) > max(2, km * 0.03):
                continue
            km = round(km or mi * 1.609344)
            if not (0 <= km <= 1_000_000 and 0 <= months <= 120 and int(months) == months and (km or months)):
                continue
            candidates.append({"service_item": services[0], "interval_km": km, "interval_months": int(months),
                               "page": page, "quote": line})
    return candidates


def summary(db, vehicle_id):
    row = db.execute("""SELECT id,title,source_url,verification,sha256,candidates
                        FROM manuals WHERE vehicle_id=? AND is_current=1""", (vehicle_id,)).fetchone()
    if not row:
        return {"manual": None, "candidates": []}
    manual = dict(row)
    candidates = json.loads(manual.pop("candidates"))
    return {"manual": manual, "candidates": candidates}


def manual_evidence(db, vehicle_id):
    return [dict(row) for row in db.execute("""
        SELECT m.id,m.title,m.source_url,m.verification,m.sha256,p.page,p.text
          FROM manuals m JOIN manual_pages p ON p.manual_id=m.id
         WHERE m.vehicle_id=? AND m.is_current=1 AND p.text <> '' ORDER BY p.page
    """, (vehicle_id,))]


def source_page(db, vehicle_id, manual_id, page):
    row = db.execute("""SELECT m.id,m.title,m.source_url,m.verification,m.sha256,p.page,p.text
                        FROM manuals m JOIN manual_pages p ON p.manual_id=m.id
                        WHERE m.vehicle_id=? AND m.id=? AND p.page=?""",
                     (vehicle_id, manual_id, page)).fetchone()
    if row is None:
        raise LookupError("Manual page not found for this vehicle.")
    return dict(row)


def import_manual(db, vehicle_id, body):
    title = body.get("title")
    if not isinstance(title, str) or not title.strip() or len(title) > 120:
        raise ValueError("Enter the manual title, model/year or edition (up to 120 characters).")
    title = " ".join(title.split())
    kinds = [kind for kind in ("text", "source_url", "file_base64") if body.get(kind)]
    if len(kinds) != 1:
        raise ValueError("Choose one source: an official link, file, or pasted text.")
    url = ""
    verification = "owner_supplied"
    media = "text/plain"
    if kinds[0] == "source_url":
        url, media, raw = download(body["source_url"])
        verification = "publisher_https"
    elif kinds[0] == "text" and isinstance(body["text"], str):
        raw = body["text"].encode()
    elif kinds[0] == "file_base64" and isinstance(body["file_base64"], str):
        try:
            raw = base64.b64decode(body["file_base64"], validate=True)
        except ValueError as exc:
            raise ValueError("The uploaded file could not be decoded.") from exc
    else:
        raise ValueError("Invalid manual input.")
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Choose a manual or section no larger than 16 MiB.")
    pages = pages_from(raw, media)
    digest = hashlib.sha256(raw).hexdigest()
    candidates = extract_intervals(pages)
    # Begin the write transaction after download and parsing. Any failure leaves the old manual active.
    db.execute("UPDATE manuals SET is_current=0 WHERE vehicle_id=? AND is_current=1", (vehicle_id,))
    archived = db.execute("""SELECT id FROM manuals
                             WHERE vehicle_id=? AND sha256=? AND title=? AND source_url=?
                             ORDER BY id DESC LIMIT 1""", (vehicle_id, digest, title, url)).fetchone()
    if archived:
        db.execute("UPDATE manuals SET is_current=1 WHERE id=?", (archived["id"],))
    else:
        manual = db.execute("""INSERT INTO manuals(vehicle_id,title,sha256,source_url,verification,candidates)
                              VALUES(?,?,?,?,?,?)""", (vehicle_id, title, digest, url, verification, json.dumps(candidates)))
        db.executemany("INSERT INTO manual_pages(manual_id,page,text) VALUES(?,?,?)",
                       ((manual.lastrowid, number, text) for number, text in enumerate(pages, 1)))
    return summary(db, vehicle_id)


def confirm_interval(db, vehicle_id, body):
    if body.get("owner_confirmed") is not True:
        raise ValueError("Review the quoted passage and confirm that it applies to your vehicle.")
    if type(body.get("manual_id")) is not int or type(body.get("candidate_index")) is not int:
        raise ValueError("Select a suggested interval from the current manual.")
    # Get a write lock before checking the active version so an import cannot interleave with confirmation.
    if not db.in_transaction:
        db.execute("BEGIN IMMEDIATE")
    current = summary(db, vehicle_id)
    manual = current["manual"]
    index = body["candidate_index"]
    if not manual or manual["id"] != body["manual_id"] or not 0 <= index < len(current["candidates"]):
        raise ValueError("This manual or suggestion has changed. Reload the current manual.")
    item = current["candidates"][index]
    ref = f'{manual["title"]}, p./section {item["page"]} (manual #{manual["id"]}, {manual["sha256"][:12]}). '
    ref += item["quote"][:300 - len(ref)]
    db.execute("""INSERT INTO reminders(vehicle_id,service_item,interval_km,interval_months,reference)
                  VALUES(?,?,?,?,?) ON CONFLICT(vehicle_id,service_item) DO UPDATE SET
                  interval_km=excluded.interval_km,interval_months=excluded.interval_months,reference=excluded.reference""",
               (vehicle_id, item["service_item"], item["interval_km"], item["interval_months"], ref))
    return {"ok": True, "reference": ref}
