"""F.2.2 Coordinate Vehicle Maintenance Information; mechanism C.2.

ICOM boundary: validated owner requests, returned records and AI outcomes are
inputs; owner policy, AI limits and referenced interval rules are controls;
confirmed writes, queries and prepared vehicle information are outputs.
This local prototype implements the manual-record path and can request an
unconfirmed draft from an opt-in local runtime.
"""

import calendar
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation

# SR08 baseline distance is 500 international miles; records use kilometres.
UPCOMING_DAYS = 30
UPCOMING_DISTANCE_KM = Decimal('500') * Decimal('1.609344')


class OperationConflict(ValueError):
    """The same save token was reused for different record fields."""


class OperationGone(LookupError):
    """The confirmed record identified by a previous save was deleted."""


class PossibleDuplicate(ValueError):
    def __init__(self, matches):
        super().__init__("Review the existing records with the same date, shop and amount before saving.")
        self.matches = matches


def validate_and_route_owner_request(validated_owner_service_request, *,
                                     owner_authorization_and_confirmation_policy,
                                     configuration_and_maintenance_instructions,
                                     record_store, field_validator):
    """F.2.2.1 / C.2.1: validate and route the local manual-record operation.

    Input: requested operation, selected vehicle and entered record fields.
    Controls: local-demo mode and the explicit-confirmation policy.
    Output: a validated transaction request, or a rejected request.
    Owner identity is not verified by this local-demo implementation.
    """
    policy = owner_authorization_and_confirmation_policy
    if policy.get("mode") != "local_demo":
        raise NotImplementedError("Owner authentication is not implemented.")
    operation = validated_owner_service_request.get("operation", "create_record")
    if operation not in configuration_and_maintenance_instructions["operations"]:
        raise ValueError("Unsupported service operation.")
    raw = validated_owner_service_request.get("vehicle_id")
    if isinstance(raw, bool) or not str(raw).isdigit() or int(raw) < 1:
        raise ValueError("vehicle_id must be a positive whole number.")
    car_id = int(raw)
    if record_store.execute("SELECT id FROM vehicles WHERE id=?", (car_id,)).fetchone() is None:
        raise LookupError("Vehicle not found.")
    key = validated_owner_service_request.get("operation_id")
    if key is not None and (not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9-]{16,80}", key)):
        raise ValueError("operation_id must be 16 to 80 letters, digits or hyphens.")
    check_duplicates = validated_owner_service_request.get("check_duplicates", False)
    reviewed = validated_owner_service_request.get("acknowledged_duplicate_ids", [])
    if not isinstance(check_duplicates, bool) or not isinstance(reviewed, list) or any(
            type(record_id) is not int or record_id < 1 for record_id in reviewed):
        raise ValueError("Duplicate review requires a boolean check_duplicates and positive record IDs.")
    if reviewed and not check_duplicates:
        raise ValueError("A duplicate acknowledgement requires check_duplicates.")
    fields = field_validator(validated_owner_service_request)
    return {"operation": operation, "vehicle_id": car_id,
            "fields": fields, "service_items": checked_service_items(validated_owner_service_request, fields[1]),
            "owner_confirmed": validated_owner_service_request.get("owner_confirmed") is True,
            "operation_id": key, "check_duplicates": check_duplicates, "acknowledged_duplicate_ids": reviewed}


def coordinate_ai_requests_and_responses(receipt_or_question_request, *,
                                        configured_ai_service_contract_limits,
                                        authorized_records_and_source_references):
    """F.2.2.2 / C.2.2: request a receipt draft and check it before owner review.

    Input: receipt text or one image bound to the local drafter. Control: configured service limits.
    Output: form values plus per-field evidence, or an exception the caller turns
    into an explicit unavailable response. Question answering remains unavailable.
    """
    limits = configured_ai_service_contract_limits
    drafter = limits.get("receipt_drafter")
    if drafter is None or receipt_or_question_request.get("kind") != "receipt":
        raise NotImplementedError("This AI operation is unavailable.")
    text = receipt_or_question_request.get("receipt_text")
    return review_receipt_draft(drafter(text or ""), text,
                                services=limits.get("services", SERVICE_ITEMS),
                                today=limits.get("today") or date.today())


SERVICE_ITEMS = ("Oil change", "Tire rotation", "Brake service", "Inspection", "Battery", "Other")


def checked_service_items(body, primary):
    """The ordered, owner-confirmed service list for a single invoice."""
    if "service_items" not in body:
        return [primary]
    items = body["service_items"]
    if (not isinstance(items, list) or not 1 <= len(items) <= len(SERVICE_ITEMS)
            or items[0] != primary or any(item not in SERVICE_ITEMS for item in items)
            or len(set(items)) != len(items)):
        raise ValueError("Choose each supported service once, with the primary service first.")
    return items


def insert_additional_services(db, record_id, items):
    db.executemany(
        "INSERT INTO record_additional_services(record_id, position, service_item) VALUES(?,?,?)",
        ((record_id, position, service) for position, service in enumerate(items[1:], 1)))


SERVICE_WORDS = {"Oil change": ("oil",), "Tire rotation": ("rotat",), "Brake service": ("brake",),
                 "Inspection": ("inspect",), "Battery": ("battery",)}
MILES_TO_KM = Decimal("1.609344")
# The amount paid, printed right after its label. "Subtotal", line items and a total
# mentioned inside a sentence (for example an injected instruction) do not count.
TOTAL_LABEL = (r"(?<![a-z])(?<!sub-)(?<!sub )(?:grand )?(?:total(?: due| paid)?|amount due|balance due)"
               r"[\s:]*(?:usd\s*)?\$?\s*")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december")


def _plain(text):
    """Lower-case text with single spaces and no period after an abbreviation."""
    return re.sub(r"\s+", " ", re.sub(r"(?<=[a-z])\.", "", str(text).lower()))


def _number_in(text, digits):
    """True if the digits appear as a whole number, with or without thousands separators."""
    grouped = f"{int(digits):,}"
    for form in {digits, grouped, grouped.replace(",", " "), grouped.replace(",", ".")}:
        if re.search(r"(?<![\d.,])" + re.escape(form) + r"(?![\d]|[.,]\d)", text):
            return True
    return False


def _date_forms(day):
    month = MONTHS[day.month - 1]
    names = {month, month[:3]} | ({"sept"} if day.month == 9 else set())
    forms = {day.isoformat(), f"{day.year}/{day.month:02}/{day.day:02}"}
    for m in {str(day.month), f"{day.month:02}"}:
        for d in {str(day.day), f"{day.day:02}"}:
            for y in {str(day.year), f"{day.year % 100:02}"}:
                forms |= {f"{m}/{d}/{y}", f"{m}-{d}-{y}", f"{m}.{d}.{y}"}
    for name in names:
        forms |= {f"{name} {day.day}, {day.year}", f"{name} {day.day} {day.year}",
                  f"{day.day} {name} {day.year}", f"{name} {day.day:02}, {day.year}"}
    return forms


def review_receipt_draft(draft, receipt_text, *, services=SERVICE_ITEMS, today=None):
    """Containment for a well-formed but possibly wrong model draft (F.2.2.2).

    Every value is validated on its own; an invalid value becomes missing instead of
    failing the whole draft. Each kept value is then looked up in the receipt text.
    Values the receipt does not support are flagged so the owner checks them.
    Status per field: found (on the receipt), check (owner must verify), missing.
    Nothing here writes a record: the owner still has to Confirm & save.
    """
    today = today or date.today()
    text = _plain(receipt_text)
    proposal, evidence = {}, {}

    def keep(field, value, status, note):
        if receipt_text is None and value is not None:
            status, note = "check", "Compare this value with the original receipt image."
            if field == "mileage" and draft.get("odometer_unit") == "mi":
                note = f"Model read {draft['odometer_value']:,} mi, converted to {value:,} km. Check the image."
        proposal[field] = value
        evidence[field] = {"status": status, "note": note}

    # Service date.
    raw = draft.get("service_date")
    try:
        day = date.fromisoformat(raw) if isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) else None
    except ValueError:
        day = None
    if day is None:
        keep("service_date", None, "missing", "Not found on the receipt. Enter the service date.")
    elif day > today:
        keep("service_date", None, "missing", "The drafted date is in the future. Enter the service date.")
    elif any(form in text for form in _date_forms(day)):
        keep("service_date", day.isoformat(), "found", "Found on the receipt.")
    else:
        keep("service_date", day.isoformat(), "check", "This date is not printed on the receipt. Check it.")

    # Service item (a classification from the receipt wording).
    item = draft.get("service_item")
    if item not in services:
        keep("service_item", None, "missing", "No supported service found. Choose one.")
    elif item in SERVICE_WORDS and any(word in text for word in SERVICE_WORDS[item]):
        keep("service_item", item, "found", "Matches the receipt wording.")
    else:
        keep("service_item", item, "check", "Not stated in those words on the receipt. Check it.")

    # Category is always a judgment, so the owner confirms it.
    category = draft.get("category")
    if category in ("Maintenance", "Repair"):
        keep("category", category, "check", "Suggested by the AI. Confirm Maintenance or Repair.")
    else:
        keep("category", None, "missing", "Choose Maintenance or Repair.")

    # Odometer: the model copies the printed number and unit; the app converts.
    value, unit = draft.get("odometer_value"), draft.get("odometer_unit")
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10_000_000:
        keep("mileage", None, "missing", "No odometer reading on the receipt. Enter the mileage.")
    else:
        km = int((Decimal(value) * MILES_TO_KM).to_integral_value()) if unit == "mi" else value
        printed = _number_in(text, str(value))
        if not printed:
            keep("mileage", km, "check", "This odometer reading is not printed on the receipt. Check it.")
        elif unit == "mi":
            keep("mileage", km, "found", f"Receipt shows {value:,} mi, converted to {km:,} km.")
        elif unit == "km":
            keep("mileage", km, "found", "Found on the receipt.")
        else:
            keep("mileage", km, "check", f"Receipt shows {value:,} with no unit. Entered as km; check km or miles.")

    # Cost: the final total, at most two decimals.
    try:
        amount = Decimal(str(draft.get("cost")).replace("$", "").replace(",", "").strip())
        if not amount.is_finite() or not 0 <= amount <= 1_000_000 or amount != amount.quantize(Decimal("0.01")):
            amount = None
    except InvalidOperation:
        amount = None
    if draft.get("cost") is None or amount is None:
        keep("cost", None, "missing", "No total found. Enter the cost.")
    else:
        cents = f"{amount:.2f}"
        forms = {cents, f"{amount:,.2f}"}

        def printed(prefix):
            return any(re.search(prefix + re.escape(form) + r"(?!\d)", text) for form in forms)

        if printed(TOTAL_LABEL):
            keep("cost", cents, "found", "Matches the total on the receipt.")
        elif printed(r"(?<![\d.,])"):
            keep("cost", cents, "check", "This amount is on the receipt but not next to the total. "
                                         "Check that it is the final total.")
        else:
            keep("cost", cents, "check", "This amount is not printed on the receipt. Check the total.")

    # Provider.
    provider = draft.get("provider")
    if not isinstance(provider, str) or not provider.strip() or len(provider.strip()) > 120:
        keep("provider", None, "missing", "No shop name found. Add it if you like.")
    elif _plain(provider.strip()) in text:
        keep("provider", provider.strip(), "found", "Found on the receipt.")
    else:
        keep("provider", provider.strip(), "check", "This name is not printed on the receipt. Check it.")

    # Multiple performed services share one invoice total. Each is a draft suggestion.
    # Keep the six scored proposal fields stable for clients and historical evaluations.
    suggested = [item] if item in services else []
    additional = draft.get("service_items")
    if isinstance(additional, list):
        for service in additional:
            if service in services and service not in suggested:
                suggested.append(service)
    return {"proposal": proposal, "evidence": evidence, "service_items": suggested}


def _matching_receipts(db, vehicle_id, fields):
    # A blank shop is weak evidence: two unknown shops need not be the same shop.
    provider = " ".join(fields[5].casefold().split())
    if not provider:
        return []
    cursor = db.execute(
        "SELECT id,service_date,service_item,provider,cost_cents,mileage FROM records "
        "WHERE vehicle_id=? AND service_date=? AND cost_cents=? ORDER BY id DESC",
        (vehicle_id, fields[0], fields[4]))
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor
            if " ".join(row[3].casefold().split()) == provider]


def coordinate_confirmed_record_transaction(confirmed_transaction_request, *,
                                            owner_authorization_and_confirmation_policy,
                                            record_store):
    """F.2.2.3 / C.2.3: persist an explicitly confirmed manual record.

    Input: validated transaction with confirmed fields and selected vehicle.
    Control: explicit owner confirmation required by the local-demo policy.
    Output: stored record confirmation containing the committed record ID.
    C.3 is the SQLite mechanism reached through this in-process boundary.
    """
    if owner_authorization_and_confirmation_policy.get("require_confirmation") is not True:
        raise ValueError("The confirmation policy must remain enabled.")
    if confirmed_transaction_request.get("owner_confirmed") is not True:
        raise ValueError("Explicit confirmation is required before saving a record.")
    request = confirmed_transaction_request
    key = request.get("operation_id")
    check_duplicates = request.get("check_duplicates", False)
    fingerprint = None
    # Serialize duplicate checks with insertion, even for clients without a retry key.
    if key is not None or check_duplicates:
        record_store.execute("BEGIN IMMEDIATE")
    if key is not None:
        # Keep legacy one-service fingerprints valid across an in-place upgrade.
        fields = request["fields"]
        additional = request.get("service_items", [fields[1]])[1:]
        signed_fields = [*fields, sorted(additional)] if additional else fields
        encoded_fields = json.dumps(signed_fields, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        fingerprint = hashlib.sha256(encoded_fields).hexdigest()
        prior = record_store.execute(
            "SELECT fingerprint, record_id, deleted FROM record_operations WHERE vehicle_id=? AND operation_id=?",
            (request["vehicle_id"], key)).fetchone()
        if prior is not None:
            record_store.rollback()
            if prior[0] != fingerprint:
                raise OperationConflict("This save token already belongs to a different record.")
            if prior[2]:
                raise OperationGone("This save already completed and the record was later deleted.")
            return {"id": prior[1]}
    if check_duplicates:
        matches = _matching_receipts(record_store, request["vehicle_id"], request["fields"])
        reviewed = set(request.get("acknowledged_duplicate_ids", []))
        if any(row["id"] not in reviewed for row in matches):
            record_store.rollback()
            raise PossibleDuplicate(matches)
    cursor = record_store.execute(
        "INSERT INTO records(vehicle_id,service_date,service_item,category,mileage,cost_cents,provider,notes) "
        "VALUES(?,?,?,?,?,?,?,?)", (request["vehicle_id"], *request["fields"]))
    if len(request.get("service_items", [])) > 1:
        insert_additional_services(record_store, cursor.lastrowid, request["service_items"])
    record_store.execute("UPDATE vehicles SET mileage=max(mileage,?) WHERE id=?",
                         (request["fields"][3], request["vehicle_id"]))
    if key is not None:
        record_store.execute(
            "INSERT INTO record_operations(vehicle_id,operation_id,fingerprint,record_id) VALUES(?,?,?,?)",
            (request["vehicle_id"], key, fingerprint, cursor.lastrowid))
    record_store.commit()
    return {"id": cursor.lastrowid}


def add_months(day, months):
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def calculate_maintenance_summary_and_reminders(authorized_records,
                                               referenced_maintenance_interval_rules, *,
                                               vehicle_context, as_of):
    """F.2.2.4 / C.2.4: prepare vehicle information from confirmed history.

    Inputs: records already retrieved for the selected vehicle.
    Controls: referenced interval rules and the observation date.
    Output: recorded costs, reminders and supporting record IDs.
    Unconfirmed AI proposals are not accepted as a record source.
    """
    records = list(authorized_records)
    months, reminders = {}, []
    for row in records:
        key = row["service_date"][:7]
        months.setdefault(key, {"Maintenance": 0, "Repair": 0})[row["category"]] += row["cost_cents"]
    for rule in referenced_maintenance_interval_rules:
        item = dict(rule)
        matching = [r for r in records if rule["service_item"] in r.get("service_items", [r["service_item"]])]
        item.update(status="Needs service history", due_date=None, due_mileage=None, record_id=None)
        if matching:
            last = matching[0]
            due_date = add_months(date.fromisoformat(last["service_date"]), rule["interval_months"]) if rule["interval_months"] else None
            due_km = last["mileage"] + rule["interval_km"] if rule["interval_km"] else None
            days_left = (due_date-as_of).days if due_date else None
            km_left = Decimal(str(due_km))-Decimal(str(vehicle_context["mileage"])) if due_km is not None else None
            status = "Scheduled"
            if (days_left is not None and days_left <= 0) or (km_left is not None and km_left <= 0):
                status = "Due / overdue"
            elif (days_left is not None and days_left <= UPCOMING_DAYS) or (km_left is not None and km_left <= UPCOMING_DISTANCE_KM):
                status = "Upcoming"
            item.update(status=status, due_date=due_date.isoformat() if due_date else None,
                        due_mileage=due_km, record_id=last["id"])
        reminders.append(item)
    return {"vehicle": vehicle_context, "records": records, "reminders": reminders,
            "total_cents": sum(r["cost_cents"] for r in records),
            "monthly": [{"month": m, **months[m]} for m in sorted(months, reverse=True)]}
