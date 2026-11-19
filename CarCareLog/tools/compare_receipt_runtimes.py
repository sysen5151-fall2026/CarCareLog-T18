"""Compare the pinned local and hosted models on the Lab 13 labeled receipt set."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from evaluate_receipts import FIELDS, SAMPLES, evaluate, load_samples, runtime


HOSTED_MODEL = "gpt-6.1-sol"
HOSTED_ENDPOINT = "https://api.openai.com/v1/responses"
OUTPUT = Path(__file__).resolve().parents[2] / "docs/evidence/lab13-receipt-comparison"
DEADLINE = 60


def hosted_drafter(key):
    schema = json.loads(json.dumps(runtime.DRAFT_SCHEMA))
    for field in ("service_item", "category", "odometer_unit"):
        schema["properties"][field]["type"] = ["string", "null"]

    def draft(receipt_text):
        prompt = runtime.build_request(receipt_text, HOSTED_MODEL)["prompt"]
        payload = {
            "model": HOSTED_MODEL,
            "input": prompt,
            "store": False,
            "reasoning": {"effort": "low"},
            "max_output_tokens": 768,
            "text": {"format": {
                "type": "json_schema", "name": "receipt_draft",
                "schema": schema, "strict": True,
            }},
        }
        request = Request(
            HOSTED_ENDPOINT, data=json.dumps(payload).encode(), method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        try:
            with urlopen(request, timeout=DEADLINE) as response:
                result = json.load(response)
            content = [part["text"] for item in result.get("output", [])
                       for part in item.get("content", []) if part.get("type") == "output_text"]
            draft = json.loads("".join(content))
        except HTTPError as exc:
            raise runtime.ReceiptRuntimeUnavailable(f"Hosted runtime HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, ValueError, TypeError, KeyError) as exc:
            raise runtime.ReceiptRuntimeUnavailable("Hosted runtime returned no usable draft.") from exc
        if not isinstance(draft, dict) or set(draft) != set(runtime.DRAFT_FIELDS):
            raise runtime.ReceiptRuntimeUnavailable("Hosted draft did not match the contract.")
        return draft
    return draft


def measure(samples, drafter):
    results = []
    for sample in samples:
        entry = evaluate([sample], drafter)[0]
        if not results and entry.get("error") in (
            "Hosted runtime HTTP 400.", "Hosted runtime HTTP 401.",
            "Hosted runtime HTTP 403.", "Hosted runtime HTTP 404.",
            "Hosted runtime HTTP 429.",
        ):
            raise SystemExit(entry["error"])
        results.append(entry)
        print(f"{entry['id']} {entry['seconds']:.3f} s"
              + (f" ({entry['error']})" if entry["error"] else ""), flush=True)
    completed = [row for row in results if "fields" in row]
    durations = sorted(row["seconds"] for row in results[1:] if "fields" in row)
    correct = sum(field["outcome"].startswith("correct")
                  for row in completed for field in row["fields"].values())
    p95 = durations[math.ceil(.95 * len(durations)) - 1] if durations else None
    expected = len(samples) * len(FIELDS)
    return {
        "first_request_seconds": results[0]["seconds"],
        "requests": len(samples), "completed": len(completed),
        "failures": len(samples) - len(completed),
        "expected_fields": expected, "correct_fields": correct,
        "field_accuracy": correct / expected,
        "warm_median_seconds": statistics.median(durations) if durations else None,
        "warm_p95_seconds": p95,
        "v5": max(0.0, 1 - p95 / 2) if p95 is not None else None,
        "review_seconds_included": False,
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=["local", "hosted"])
    args = parser.parse_args()
    samples = load_samples()
    if args.provider == "hosted":
        key = os.environ.get("OPENAI_API_KEY")
        if not key:
            raise SystemExit("OPENAI_API_KEY is missing from this process.")
        run = {"model": HOSTED_MODEL, "endpoint": HOSTED_ENDPOINT, "reasoning_effort": "low"}
        drafter = hosted_drafter(key)
    else:
        run = runtime.runtime_details(runtime.PINNED_MODEL)
        if not run["weights_digest_matches_pin"]:
            raise SystemExit("The installed local weights do not match the pinned digest.")

        def drafter(text):
            return runtime.draft_receipt(text, runtime.PINNED_MODEL)

    run["provider"] = args.provider
    run["samples"] = SAMPLES.name
    run["samples_sha256"] = hashlib.sha256(SAMPLES.read_bytes()).hexdigest()
    run["started_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run.update(measure(samples, drafter))
    run["completed_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    target = OUTPUT.with_name(OUTPUT.name + "-" + args.provider).with_suffix(".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
