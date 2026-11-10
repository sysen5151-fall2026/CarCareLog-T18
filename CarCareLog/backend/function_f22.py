"""F.2.2 Coordinate Vehicle Maintenance Information; mechanism C.2.

ICOM boundary: validated owner requests, returned records and AI outcomes are
inputs; owner policy, AI limits and referenced interval rules are controls;
confirmed writes, queries and prepared vehicle information are outputs.
This local prototype implements the manual-record path. It does not authenticate
owners, extract receipts or call an external AI runtime.
"""

import calendar
import hashlib
import json
import re
from datetime import date
from decimal import Decimal

# SR08 baseline distance is 500 international miles; records use kilometres.
UPCOMING_DAYS = 30
UPCOMING_DISTANCE_KM = Decimal('500') * Decimal('1.609344')


class OperationConflict(ValueError):
    """The same save token was reused for different record fields."""


class OperationGone(LookupError):
    """The confirmed record identified by a previous save was deleted."""


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
    return {"operation": operation, "vehicle_id": car_id,
            "fields": field_validator(validated_owner_service_request),
            "owner_confirmed": validated_owner_service_request.get("owner_confirmed") is True,
            "operation_id": key}


def coordinate_ai_requests_and_responses(receipt_or_question_request, *,
                                        configured_ai_service_contract_limits,
                                        authorized_records_and_source_references):
    """F.2.2.2 / C.2.2: reserved external-AI boundary, not implemented.

    Inputs and controls follow the modeled AI/evidence boundary. This function
    deliberately raises rather than fabricating an extraction or AI response.
    The implemented manual path does not depend on this boundary.
    """
    raise NotImplementedError("External AI coordination remains planned.")


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
    fingerprint = None
    if key is not None:
        encoded_fields = json.dumps(request["fields"], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        fingerprint = hashlib.sha256(encoded_fields).hexdigest()
        # Check and claim the key under the same writer lock as the record insert.
        record_store.execute("BEGIN IMMEDIATE")
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
    cursor = record_store.execute(
        "INSERT INTO records(vehicle_id,service_date,service_item,category,mileage,cost_cents,provider,notes) "
        "VALUES(?,?,?,?,?,?,?,?)", (request["vehicle_id"], *request["fields"]))
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
        matching = [r for r in records if r["service_item"] == rule["service_item"]]
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
