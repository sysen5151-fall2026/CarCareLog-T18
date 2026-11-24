"""Create one local-calendar event for an existing dated maintenance interval."""
import unicodedata
from datetime import date, datetime, timedelta, timezone


def calendar_text(value):
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(char for char in text if char == "\n" or unicodedata.category(char) != "Cc")
    return text.replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def fold(line):
    """RFC 5545 limits physical lines to 75 octets, including a continuation space."""
    result = bytearray()
    width = 0
    for char in line:
        encoded = char.encode("utf-8")
        if width + len(encoded) > 75:
            result.extend(b"\r\n ")
            width = 1
        result.extend(encoded)
        width += len(encoded)
    return bytes(result)


def reminder_event(db, vehicle, rule, *, today=None):
    today = today or date.today()
    if not rule["due_date"]:
        raise ValueError("A calendar event needs a due date calculated from a confirmed service and month interval.")
    due = date.fromisoformat(rule["due_date"])
    if due <= today or rule["status"] == "Due / overdue":
        raise ValueError("Service is already due. Review the reminder in CarCareLog.")

    # Older installations also get stable, ledger-specific event IDs on their first export.
    db.execute("""CREATE TABLE IF NOT EXISTS calendar_reminder_ids (
        rule_id INTEGER PRIMARY KEY REFERENCES reminders(id) ON DELETE CASCADE, uid TEXT UNIQUE NOT NULL)""")
    db.execute("""INSERT OR IGNORE INTO calendar_reminder_ids(rule_id,uid)
                  VALUES(?, lower(hex(randomblob(16))))""", (rule["id"],))
    identity = db.execute("SELECT uid FROM calendar_reminder_ids WHERE rule_id=?", (rule["id"],)).fetchone()[0]
    day = due.strftime("%Y%m%d")
    title = calendar_text(f'{rule["service_item"]} — {vehicle["name"]}')
    description = "Review this maintenance interval in CarCareLog."
    if rule["due_mileage"] is not None:
        description += f' Service is due earlier if the odometer reaches {rule["due_mileage"]:,} km first.'
    # Floating 09:00 follows the recipient's calendar time zone. For a next-day event,
    # use its start time so the calendar does not receive a potentially elapsed alert.
    trigger = "PT0S" if due == today + timedelta(days=1) else "-P1D"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CarCareLog T18//Maintenance//EN",
        "CALSCALE:GREGORIAN", "BEGIN:VEVENT", f"UID:{identity}-{day}@carcarelog.local",
        f"DTSTAMP:{stamp}", f"DTSTART:{day}T090000", "DURATION:PT15M", "TRANSP:TRANSPARENT",
        f"SUMMARY:{title}", "DESCRIPTION:" + calendar_text(description),
        "BEGIN:VALARM", f"TRIGGER:{trigger}", "ACTION:DISPLAY", f"DESCRIPTION:{title}",
        "END:VALARM", "END:VEVENT", "END:VCALENDAR",
    ]
    return b"\r\n".join(fold(line) for line in lines) + b"\r\n"
