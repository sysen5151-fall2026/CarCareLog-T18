"""Read-only answers derived from the selected vehicle's records and manual pages."""

import calendar
import json
import re
from collections import Counter
from datetime import date
from http.client import HTTPException

try:
    from . import receipt_runtime
except ImportError:
    import receipt_runtime


SERVICES = {
    "Oil change": r"\b(?:oil(?: changes?)?|lube)\b",
    "Tire rotation": r"\b(?:tires?|tyres?|wheel) rotations?\b|\brotat(?:ed|e|ing) (?:my |the )?(?:tires?|tyres?)\b",
    "Brake service": r"\bbrakes?\b",
    "Inspection": r"\binspections?\b",
    "Battery": r"\bbatter(?:y|ies)\b",
}
MONTHS = {name.lower(): month for month in range(1, 13)
          for name in (calendar.month_name[month], calendar.month_abbr[month])}
MONTH_PATTERN = r"\b(" + "|".join(MONTHS) + r")\b"
STOP_WORDS = set("""a an the and or of for to in into on at about as by with from do does did i my me
    mine this that is are was were has have had how when what which who where much many often can
    could would should will tell show give get find list me please all any ever over most recent
    last first latest recorded records record service services history vehicle car manual owners
    owner handbook manufacturers manufacturer according says say recommend recommended schedule
    says it its our my their need needs check should did done been times""".split())


def _tokens(text):
    tokens = re.findall(r"[^\W_]+", text.casefold(), re.UNICODE)
    aliases = {"tyres": "tire", "tyre": "tire", "wheels": "wheel", "pressure": "pressure",
               "oilchange": "oil", "lubricant": "oil", "rotation": "rotate", "rotating": "rotate",
               "rotated": "rotate", "inflation": "pressure", "inflated": "pressure",
               "viscosity": "grade", "intervals": "interval"}
    return {aliases.get(t, t.rstrip("s") if len(t) > 4 and t.endswith("s") else t)
            for t in tokens if t not in STOP_WORDS and len(t) > 1}


def _result(message, method="Insufficient evidence", rows=(), pages=()):
    return {"answer": message, "method": method, "record_ids": [r["id"] for r in rows],
            "manual_sources": list(pages)}


def _date_filter(query, today):
    """Return an inclusive ISO range, a label, and the unconsumed query."""
    match = re.search(r"\b(?:from|between) (\d{4}-\d\d-\d\d) (?:to|through|and) (\d{4}-\d\d-\d\d)\b", query)
    if match:
        start, end = (date.fromisoformat(x) for x in match.groups())
        if start > end:
            raise ValueError("The start of the date range must come before its end.")
        return start.isoformat(), end.isoformat(), f"{start} through {end}", query.replace(match[0], "")
    match = re.search(r"\b(last|this) (month|year)\b", query)
    if match:
        year, month = today.year, today.month
        if match[2] == "year":
            year -= match[1] == "last"
            return f"{year}-01-01", f"{year}-12-31", str(year), query.replace(match[0], "")
        if match[1] == "last":
            month -= 1
            if not month:
                year, month = year - 1, 12
        return (f"{year}-{month:02}-01", f"{year}-{month:02}-{calendar.monthrange(year, month)[1]}",
                f"{calendar.month_name[month]} {year}", query.replace(match[0], ""))
    exact = re.search(r"\b\d{4}-\d\d-\d\d\b", query)
    if exact:
        value = date.fromisoformat(exact[0]).isoformat()
        return value, value, value, query.replace(exact[0], "")
    years = re.findall(r"\b(?:19|20)\d{2}\b", query)
    month = re.search(MONTH_PATTERN, query)
    if len(years) > 1 or (month and not years):
        return "", "", "", query
    if years:
        year = int(years[0])
        if month:
            number = MONTHS[month[0]]
            return (f"{year}-{number:02}-01", f"{year}-{number:02}-{calendar.monthrange(year, number)[1]}",
                    f"{calendar.month_name[number]} {year}", query.replace(years[0], "").replace(month[0], ""))
        return f"{year}-01-01", f"{year}-12-31", str(year), query.replace(years[0], "")
    return "", "", "", query


def _row_text(row):
    services = row.get("service_items") or [row["service_item"]]
    return (f'#{row["id"]} | {row["service_date"]} | {", ".join(services)} | {row["category"]} | '
            f'{row["mileage"]:,} km | invoice ${row["cost_cents"] / 100:,.2f} | '
            f'{row.get("provider") or "no provider recorded"}')


def _record_answer(question, records, today):
    """Resolve natural questions with well-defined filters; consume every material qualifier."""
    query = re.sub(r"\s+", " ", question.lower().replace("’", "'"))
    query = re.sub(r"\boil (?:was )?changed\b|\bchanged (?:my |the )?oil\b", "oil change", query)
    rows = list(records)
    labels = []
    for provider in sorted({r["provider"] for r in rows if r.get("provider")}, key=len, reverse=True):
        match = re.search(r"(?<!\w)" + re.escape(provider.casefold()) + r"(?!\w)", query)
        if match:
            labels.append(provider)
            rows = [r for r in rows if (r.get("provider") or "").casefold() == provider.casefold()]
            query = query[:match.start()] + " " + query[match.end():]
            break
    start, end, period, query = _date_filter(query, today)
    if period:
        labels.append(period)
        rows = [r for r in rows if start <= r["service_date"] <= end]
    services = [s for s, pattern in SERVICES.items() if re.search(pattern, query)]
    if len(services) > 1:
        return None
    service = services[0] if services else None
    if service:
        query = re.sub(SERVICES[service], "", query)
        rows = [r for r in rows if service in (r.get("service_items") or [r["service_item"]])]
        labels.append(service)
    category = re.search(r"\b(repairs?|maintenance)\b", query)
    # "maintenance records/history" can refer to all records; treat as a category only with cost/count language.
    if category and (category[1].startswith("repair") or re.search(r"\b(spend|spent|spending|cost|paid|category)\b", query)):
        name = "Repair" if category[1].startswith("repair") else "Maintenance"
        rows = [r for r in rows if r["category"] == name]
        labels.append(name)
        query = query.replace(category[0], "")
    expensive = re.search(r"\b(most expensive|highest|largest|biggest|cheapest|lowest|least expensive)\b", query)
    earliest = re.search(r"\b(first|earliest|oldest)\b", query)
    latest = re.search(r"\b(last|latest|most recent|newest)\b", query)
    count = re.search(r"\b(how many|number of|count)\b", query)
    currency_count = re.search(r"\b(?:how many|number of) dollars?\b", query)
    sum_cost = currency_count or re.search(r"\b(total|spend|spent|paid|spending|costs?|pay|much|amount)\b", query)
    odometer = re.search(r"\b(?:mileage|odometer|kilometers?|km)\b", query)
    supported = (expensive or earliest or latest or count or sum_cost or
                 re.search(r"\b(show|list|which|find)\b", query) or service)
    vocabulary = """spend spent spending paid pay payment cost costs amount total totals bill bills invoice
        invoices dollars money number count highest lowest largest biggest expensive least cheapest
        newest earliest oldest provider shop shops date mileage odometer kilometer kilometers km
        change changes changed changing maintenance repair repairs category categorized work performed
        receipts receipt purchase purchases visit visits fees""".split()
    if not supported or "how often" in query or _tokens(query) - _tokens(" ".join(vocabulary)):
        return None
    if odometer and not (expensive or latest or earliest):
        # Adding cumulative odometer readings would not measure distance traveled.
        return None
    scope = ", ".join(labels) if labels else "all confirmed records"
    if not rows:
        return _result(f"No confirmed records match this vehicle and selection ({scope}).")
    if expensive or latest or earliest:
        if expensive:
            best = min if expensive[0] in {"cheapest", "lowest", "least expensive"} else max
            if odometer and (sum_cost or expensive[0] not in {"highest", "lowest"}):
                return None  # Mixed metrics need clarification.
            field = "mileage" if odometer else "cost_cents"
            value = best(r[field] for r in rows)
            selected = [r for r in rows if r[field] == value]
            label = ("Lowest" if best is min else "Highest") + (" recorded mileage" if odometer else " invoice")
        else:
            selected = [rows[-1] if earliest else rows[0]]
            label = "Earliest confirmed record" if earliest else "Latest confirmed record"
        answer = f"{label} ({scope}): " + _row_text(selected[0]) + "."
        if len(selected) > 1:
            answer += f" {len(selected)} records tie at that value."
        if service and any(len(r.get("service_items", [])) > 1 for r in selected):
            answer += " The recorded amount covers the entire invoice. A separate service price is unavailable."
        return _result(answer, "Confirmed record lookup", selected)
    if count and not currency_count:
        return _result(f"Confirmed records ({scope}): {len(rows)}.", "Confirmed record count", rows)
    if sum_cost:
        known = [r for r in rows if not service or len(r.get("service_items") or [r["service_item"]]) == 1]
        total = sum(r["cost_cents"] for r in known) / 100
        if len(known) != len(rows):
            return _result(f"Single-service invoices ({scope}) total ${total:,.2f}. "
                           f"{len(rows) - len(known)} mixed-service invoice(s) have no item prices. "
                           "The exact service total is unknown.", "Confirmed invoice amounts", rows)
        return _result(f"Recorded spending ({scope}): ${total:,.2f} across {len(rows)} invoice(s).",
                       "Confirmed invoice amounts", rows)
    return _result(f"Matching confirmed records ({scope}): {len(rows)}. Open a source to see the details.",
                   "Confirmed record search", rows)


def _passages(text):
    """Bound excerpts while preserving verbatim substrings (including PDF line breaks)."""
    lines = re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", text)
    for line in lines:
        line = line.strip()
        while line:
            cut = len(line)
            if cut > 620:
                cut = max(line.rfind(" ", 200, 620), line.rfind("\n", 200, 620))
                cut = cut if cut > 0 else 620
            yield line[:cut]
            line = line[cut:].lstrip()


def _rank(terms, candidates):
    """Rare terms matter more, and single incidental hits should not answer multi-topic questions."""
    indexed = [(text, source, _tokens(text)) for text, source in candidates]
    counts = Counter(t for _, _, tokens in indexed for t in terms & tokens)
    results = []
    for text, source, tokens in indexed:
        hits = terms & tokens
        if hits and (len(terms) == 1 or len(hits) >= 2 or len(hits) / len(terms) >= .5):
            score = (len(hits), sum(1 / counts[t] for t in hits))
            results.append((score, text, source))
    results.sort(key=lambda result: result[0], reverse=True)
    return [(text, source) for _, text, source in results[:3]]


def _alternate_terms(question, model):
    """Ask Ollama for retrieval keywords only. No vehicle records or manuals go to the model."""
    schema = {"type": "object", "properties": {"terms": {"type": "array", "maxItems": 5,
              "items": {"type": "string"}}}, "required": ["terms"], "additionalProperties": False}
    payload = {"model": model, "stream": False, "format": schema, "options": receipt_runtime.GENERATION_OPTIONS,
               "keep_alive": receipt_runtime.KEEP_ALIVE,
               "prompt": "Suggest up to five alternate automotive search words for the quoted question. "
                         "Return an empty list for unrelated questions. Do not supply an answer. Question: "
                         + json.dumps(question, ensure_ascii=False)}
    if model == receipt_runtime.PINNED_MODEL:
        payload["think"] = False
    try:
        reply = receipt_runtime._call_runtime("POST", "/api/generate", payload, timeout=12)
        terms = json.loads(reply["response"])["terms"]
        if isinstance(terms, list) and len(terms) <= 5 and all(isinstance(t, str) and len(t) <= 50 for t in terms):
            return _tokens(" ".join(terms))
    except (OSError, HTTPException, KeyError, TypeError, ValueError, receipt_runtime.ReceiptRuntimeUnavailable):
        pass
    return set()


def answer_question(question, records, manual_pages, *, today, source="auto", model=""):
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 600:
        raise ValueError("Enter a question of up to 600 characters.")
    if source not in ("auto", "history", "manual"):
        raise ValueError("Choose vehicle records, the imported manual, or automatic selection.")
    question = question.strip()
    mentions_manual = re.search(r"\b(manual|handbook|recommended|manufacturer|should|how often should|"
                                r"how frequently|what pressure|tire pressure|tyre pressure|what grade|"
                                r"interval|how often do i need|viscosity)\b", question, re.I)
    manual = source == "manual" or (source == "auto" and mentions_manual)
    if not manual:
        direct = _record_answer(question, records, today)
        if direct:
            return direct
    candidates = []
    if manual or source == "auto":
        for page in manual_pages:
            for excerpt in _passages(page["text"]):
                candidates.append((excerpt, ("manual", page)))
    if not manual:
        for row in records:
            candidates.append((_row_text(row) + " " + (row.get("notes") or ""), ("record", row)))
    if not candidates:
        return _result("No imported manual is available for this vehicle." if manual else
                       "No source material is available for this vehicle and selection.")
    matches = _rank(_tokens(question), candidates)
    if not matches and model:
        alternatives = _alternate_terms(question, model)
        if alternatives:
            matches = _rank(alternatives, candidates)
    if not matches:
        return _result("I couldn't find evidence for this question in the selected vehicle's sources.")
    pages, rows = [], []
    for excerpt, (kind, item) in matches:
        if kind == "record":
            rows.append(item)
        else:
            page = {k: item[k] for k in ("id", "title", "page", "verification", "source_url")}
            pages.append({**page, "quote": excerpt})
    message = ("The imported manual gives these passages. Check the cited page for conditions that apply "
               "to your vehicle." if pages and not rows else
               "These sources contain related details. Open them to check the wording and context.")
    return _result(message, "Related source excerpts", rows, pages)
