"""Answers supported by confirmed records returned for one vehicle."""

import re


def _services(row):
    return row.get("service_items", [row["service_item"]])


def history_answer(question, records, *, year=None, today):
    """Records arrive in descending service date, mileage and ID order."""
    if question == "total":
        cents = sum(row["cost_cents"] for row in records)
        answer = f"Total recorded spending: ${cents / 100:.2f} across {len(records)} records."
        sources = records
    elif question in ("oil", "tire_rotation"):
        service = "Oil change" if question == "oil" else "Tire rotation"
        last = next((row for row in records if service in _services(row)), None)
        sources = [last] if last else []
        if last:
            answer = f'Last recorded {service.lower()}: {last["service_date"]}, at {last["mileage"]:,} km.'
        else:
            label = service.lower().replace(" ", "-")
            answer = f"Insufficient evidence: no {label} record is available."
    elif question == "brake_spending":
        year = str(today.year) if year is None else year
        if not re.fullmatch(r"[0-9]{4}", year) or year == "0000":
            raise ValueError("Choose a four-digit calendar year.")
        sources = [row for row in records if row["service_date"].startswith(year + "-")
                   and "Brake service" in _services(row)]
        if sources:
            brake_only = [row for row in sources if len(_services(row)) == 1]
            known = sum(row["cost_cents"] for row in brake_only)
            mixed_count = len(sources) - len(brake_only)
            if mixed_count:
                unallocated = ("One mixed-service receipt also includes brakes." if mixed_count == 1
                               else f"{mixed_count} mixed-service receipts also include brakes.")
                answer = (f"In {year}, brake-only receipts account for ${known / 100:.2f}. "
                          f"{unallocated} No separate brake price was recorded for that work, "
                          "so the exact brake total is unknown.")
            else:
                answer = f"Recorded brake spending in {year}: ${known / 100:.2f}."
        else:
            answer = f"Insufficient evidence: no brake-service record is available for {year}."
    else:
        raise ValueError("Choose a supported history question.")
    return {"answer": answer, "record_ids": [row["id"] for row in sources],
            "method": "Recorded-data lookup"}
