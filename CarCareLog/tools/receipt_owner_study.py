"""Local camera-photo benchmark and first-time-owner study. See docs/verification/receipt-owner-study.md."""

import argparse
import base64
from collections import Counter
from contextlib import closing
from decimal import Decimal
from hashlib import sha256
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
from statistics import median
import sys
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic
import webbrowser

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import app, receipt_runtime
from backend.function_f22 import review_receipt_draft
from evaluate_receipts import FIELDS, same

PARTICIPANTS = tuple(f"P{i:02d}" for i in range(1, 11))
MODES = ("ai", "manual")


def write_new(path, data):
    with path.open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def read_cases(folder):
    cases = json.loads((folder / "cases.json").read_text(encoding="utf-8-sig"))
    ids, hashes = set(), set()
    for case in cases:
        key = case["id"]
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,24}", key) or key in ids:
            raise ValueError("Each photo needs a unique short case ID.")
        photo = (folder / case["image"]).resolve()
        if not photo.is_relative_to(folder.resolve()) or not photo.is_file():
            raise ValueError(f"Place the assigned JPEG or PNG inside the study folder for {key}.")
        if photo.stat().st_size > receipt_runtime.MAX_IMAGE_BYTES:
            raise ValueError(f"{key} exceeds the 4 MiB product limit.")
        image = photo.read_bytes()
        receipt_runtime.validate_image(base64.b64encode(image).decode("ascii"))
        case["digest"] = sha256(image).digest()
        if case["digest"] in hashes:
            raise ValueError("Use distinct camera images for the assignments.")
        ids.add(key)
        hashes.add(case["digest"])
        if not case["condition"].strip():
            raise ValueError(f"Describe the photographic condition for {key}.")
        label = case["label"]
        if set(label) != set(FIELDS) or not str(label.get("provider") or "").strip():
            raise ValueError(f"Independently label all six fields for {key}, including the provider.")
        app.record_fields(label)  # Apply the product's constraints on dates, money and supported services.
        label["cost"] = format(Decimal(str(label["cost"])), ".2f")
        label["mileage"] = int(label["mileage"])
    if len(cases) < 2:
        raise ValueError("Supply at least two different supported camera receipts.")
    return cases


def differences(left, right):
    return [field for field in FIELDS if not same(field, left.get(field), right.get(field))]


def benchmark(folder, cases):
    results = []
    for case in cases:
        photo = base64.b64encode((folder / case["image"]).read_bytes()).decode("ascii")
        start = monotonic()
        try:
            raw = receipt_runtime.draft_receipt("", receipt_runtime.PINNED_MODEL, receipt_image=photo)
            proposal = review_receipt_draft(raw, None)["proposal"]
            wrong = differences(proposal, case["label"])
            completed = True
        except receipt_runtime.ReceiptRuntimeUnavailable:
            wrong, completed = list(FIELDS), False
        results.append({"case": case["id"], "condition": case["condition"], "draft_returned": completed,
                        "wrong_or_missing": wrong, "seconds": round(monotonic() - start, 3)})
    return {"model": receipt_runtime.PINNED_MODEL, "photos": len(results),
            "correct_fields": sum(len(FIELDS) - len(r["wrong_or_missing"]) for r in results),
            "attempted_fields": len(FIELDS) * len(results), "per_photo": results}


def study_handler(case, observation):
    """Observe the normal HTTP paths. No receipt content is written to the observation file."""
    class ObservedApp(app.Handler):
        def log_message(self, *_):
            pass

        def body(self, *args):
            body = super().body(*args)
            self.assigned_image = False
            if self.path.partition("?")[0] == "/api/receipt-draft" and "receipt_image" in body:
                validated = receipt_runtime.validate_image(body["receipt_image"])
                self.assigned_image = sha256(base64.b64decode(validated)).digest() == case["digest"]
            return body

        def reply(self, payload, status=200, **kwargs):
            route = self.path.partition("?")[0]
            if self.command == "POST" and route == "/api/receipt-draft":
                observation["draft"] = payload["proposal"] if status == 200 and self.assigned_image else None
            elif self.command == "POST" and route == "/api/records" and status == 201 and "saved_at" not in observation:
                observation.update(saved_at=monotonic(), saved_id=payload["id"], saved_draft=observation.get("draft"))
            elif self.command in ("PUT", "DELETE") and status == 200 and route == f"/api/records/{observation.get('saved_id')}":
                observation["edited_after_save"] = True
            return super().reply(payload, status, **kwargs)
    return ObservedApp


def grade(observation, start, finish, records, case, mode, helped):
    # The first confirmed row must remain the single correct row on the assigned vehicle.
    saved = next((r for r in records if r["id"] == observation.get("saved_id")), None)
    confirmed = saved is not None and len(records) == 1 and saved["vehicle_id"] == 1
    values = {**saved, "cost": f"{Decimal(saved['cost_cents']) / 100:.2f}"} if saved else {}
    wrong = differences(values, case["label"])
    if saved and set(saved.get("service_items", [saved["service_item"]])) != {case["label"]["service_item"]}:
        if "service_item" not in wrong:
            wrong.append("service_item")
    # Changes after the first save do not earn an earlier completion time.
    draft = observation.get("saved_draft")
    qualified_path = mode == "manual" or draft is not None
    correct = confirmed and not wrong and not observation.get("edited_after_save", False)
    seconds = finish - start
    return {"case": case["id"], "mode": mode, "saved": confirmed, "correct_save": correct,
            "unaided": not helped, "assigned_photo_drafted": draft is not None, "seconds": round(seconds, 3),
            "server_save_seconds": round(observation["saved_at"] - start, 3) if saved else None,
            "passed_180": bool(correct and not helped and qualified_path and seconds <= 180),
            "incorrect_saved_fields": wrong, "changed_draft_fields": differences(draft, values) if draft and saved else []}


def run_task(folder, person, mode, case):
    output = folder / f"{person}-{mode}.json"
    if output.exists():
        raise ValueError(f"A recorded {mode} trial already exists for {person}.")
    with TemporaryDirectory(prefix="carcare-owner-") as temp:
        app.DB_PATH = Path(temp) / "study.db"
        os.environ["CARCARE_OLLAMA_MODEL"] = receipt_runtime.PINNED_MODEL if mode == "ai" else ""
        app.init_db()
        with closing(app.connect()) as db, db:
            db.execute("INSERT INTO vehicles(name,mileage) VALUES ('Study vehicle',0)")
        observed = {}
        with ThreadingHTTPServer(("127.0.0.1", 0), study_handler(case, observed)) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}"
                print(f"{person} / {mode}. Open the study vehicle at {url}.")
                webbrowser.open(url)
                input("With the untouched dashboard ready, press Enter to start the timer and reveal the photo. ")
                if "saved_at" in observed or observed.get("draft"):
                    raise ValueError("The app was used before the task started. No observation recorded.")
                start = monotonic()
                print("Assigned camera photo:", folder / case["image"], flush=True)
                input("Press Enter after the owner sees the saved record or abandons the attempt. ")
                finish = monotonic()
                with closing(app.connect()) as db:
                    records = app.all_records(db, 1)
                    count = db.execute("SELECT COUNT(*) FROM records").fetchone()[0]
                    if count != len(records):
                        records = []  # Extra or misplaced records disqualify this task.
            finally:
                server.shutdown()
                thread.join()
        while (answer := input("Did the owner receive any help? [y/n] ").strip().lower()) not in ("y", "n"):
            print("Enter y or n.")
        outcome = grade(observed, start, finish, records, case, mode, answer == "y")
        write_new(output, outcome)
        print(f"Saved local observation for {person}, {mode}.")


def summarize(folder):
    ai, pairs, changed = [], [], Counter()
    for person in PARTICIPANTS:
        trials = {}
        for mode in MODES:
            file = folder / f"{person}-{mode}.json"
            if file.is_file():
                trials[mode] = json.loads(file.read_text(encoding="utf-8"))
        if "ai" in trials:
            ai.append(trials["ai"])
            changed.update(trials["ai"]["changed_draft_fields"])
        if len(trials) == 2 and trials["ai"]["assigned_photo_drafted"] and all(
                row["correct_save"] and row["unaided"] for row in trials.values()):
            pairs.append((trials["ai"]["seconds"], trials["manual"]["seconds"]))
    passing = sum(row["passed_180"] for row in ai)
    disposition = "pending" if len(ai) < 10 else ("met" if passing >= 9 else "not met")
    return {"first_time_ai_observations": len(ai), "passed_within_180s": passing, "v03": disposition,
            "did_not_meet_ai_criterion": len(ai) - passing,
            "changed_draft_fields": {field: changed[field] for field in FIELDS},
            "correct_unaided_pairs": len(pairs),
            "paired_ai_median_seconds": round(median(a for a, m in pairs), 3) if pairs else None,
            "paired_manual_median_seconds": round(median(m for a, m in pairs), 3) if pairs else None,
            "paired_median_seconds_saved_with_ai": round(median(m - a for a, m in pairs), 3) if pairs else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["init", "photos", "trial", "summary"])
    parser.add_argument("folder", type=Path)
    parser.add_argument("participant", nargs="?", choices=PARTICIPANTS)
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if args.action == "init":
        folder.mkdir(parents=True, exist_ok=True)
        write_new(folder / "cases.json", [{"id": identifier, "image": identifier + ".jpg",
                  "condition": "", "label": dict.fromkeys(FIELDS, "")} for identifier in ("A", "B")])
        print("Add de-identified camera photos and their independently checked labels to", folder)
    elif args.action == "summary":
        if not (folder / "cases.json").exists():
            parser.error("Select an initialized study folder.")
        print(json.dumps(summarize(folder), indent=2))
    else:
        cases = read_cases(folder)
        if args.action == "photos":
            print(json.dumps(benchmark(folder, cases), indent=2))
        elif args.participant:
            index = PARTICIPANTS.index(args.participant)
            for offset, mode in enumerate(MODES):
                if mode == "manual" and (folder / f"{args.participant}-manual.json").exists():
                    parser.error("This participant already finished both tasks.")
                if mode == "ai" and (folder / f"{args.participant}-ai.json").exists():
                    print("Resuming at manual comparison. The recorded first AI attempt is preserved.")
                    continue
                run_task(folder, args.participant, mode, cases[(index + offset) % len(cases)])
        else:
            parser.error("trial requires a first-time participant ID P01 to P10.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, FileExistsError, FileNotFoundError, KeyError) as exc:
        raise SystemExit(str(exc))
