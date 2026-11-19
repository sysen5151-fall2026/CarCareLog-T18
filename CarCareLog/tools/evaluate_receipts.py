"""Lab 13 evaluation of the pinned local model on the labeled receipt samples.

Run from the repository root after `ollama pull qwen2.5:3b-instruct-q4_K_M`:

    python CarCareLog/tools/evaluate_receipts.py

Each sample goes through the same path as the browser page: the runtime adapter
(receipt_runtime.draft_receipt) and then the containment check
(function_f22.review_receipt_draft). Each field is scored against its label:

    correct          value matches the label and the page shows it as found
    correct_flagged  value matches, but the page still asks the owner to check it
    wrong_flagged    value is wrong or missing, and the page flags it
    wrong_unflagged  value is wrong, and the page shows it as found  (the case that matters)

The report goes to docs/evidence/lab13-receipt-eval.md and .json.
"""

import argparse
from datetime import date, datetime, timezone
import json
import math
import platform
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "CarCareLog"))
from backend import receipt_runtime as runtime  # noqa: E402
from backend.function_f22 import _plain, review_receipt_draft  # noqa: E402

FIELDS = ("service_date", "service_item", "category", "mileage", "cost", "provider")
OUTCOMES = ("correct", "correct_flagged", "wrong_flagged", "wrong_unflagged")
SAMPLES = ROOT / "CarCareLog" / "data" / "receipt-samples.jsonl"
OUTPUT = ROOT / "docs" / "evidence" / "lab13-receipt-eval"


def load_samples(path=SAMPLES):
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def same(field, got, want):
    if got is None or want is None:
        return got is None and want is None
    if field == "provider":
        return _plain(got) == _plain(want)
    return got == want


def score(label, reviewed):
    fields = {}
    for field in FIELDS:
        got = reviewed["proposal"][field]
        status = reviewed["evidence"][field]["status"]
        if same(field, got, label[field]):
            outcome = "correct" if status == "found" else "correct_flagged"
        else:
            outcome = "wrong_unflagged" if status == "found" else "wrong_flagged"
        fields[field] = {"got": got, "want": label[field], "status": status, "outcome": outcome}
    return fields


def evaluate(samples, drafter, *, today=None, clock=time.perf_counter):
    results = []
    for sample in samples:
        started = clock()
        try:
            raw, error = drafter(sample["text"]), None
        except runtime.ReceiptRuntimeUnavailable as exc:
            raw, error = None, str(exc)
        entry = {"id": sample["id"], "focus": sample["focus"],
                 "seconds": round(clock() - started, 3), "error": error, "raw": raw}
        if raw is not None:
            reviewed = review_receipt_draft(raw, sample["text"], today=today or date.today())
            entry["fields"] = score(sample["label"], reviewed)
        results.append(entry)
    return results


def _ratio(part, whole):
    return round(part / whole, 3) if whole else None


def nearest_rank_p95(seconds):
    return sorted(seconds)[math.ceil(0.95 * len(seconds)) - 1] if seconds else None


def summarize(results):
    drafted = [r for r in results if "fields" in r]
    per_field = {}
    for field in FIELDS:
        outcomes = [r["fields"][field]["outcome"] for r in drafted]
        counts = {name: outcomes.count(name) for name in OUTCOMES}
        counts["accuracy"] = _ratio(counts["correct"] + counts["correct_flagged"], len(drafted))
        per_field[field] = counts
    totals = {name: sum(per_field[f][name] for f in FIELDS) for name in OUTCOMES}
    values = len(drafted) * len(FIELDS)
    wrong = totals["wrong_flagged"] + totals["wrong_unflagged"]
    seconds = [r["seconds"] for r in results]
    warm = seconds[1:]
    return {
        "receipts": len(results),
        "drafted": len(drafted),
        "runtime_failures": len(results) - len(drafted),
        "receipts_all_fields_correct": sum(
            all(f["outcome"].startswith("correct") for f in r["fields"].values()) for r in drafted),
        "well_formed_but_wrong_receipts": sum(
            any(f["outcome"].startswith("wrong") for f in r["fields"].values()) for r in drafted),
        "field_values": values,
        "field_accuracy": _ratio(totals["correct"] + totals["correct_flagged"], values),
        "wrong_values": wrong,
        "wrong_values_flagged": totals["wrong_flagged"],
        "wrong_values_unflagged": totals["wrong_unflagged"],
        "containment_catch_rate": _ratio(totals["wrong_flagged"], wrong),
        "correct_values_flagged_for_check": totals["correct_flagged"],
        "latency_seconds": {
            "first_request": seconds[0] if seconds else None,
            "warm_median": round(statistics.median(warm), 3) if warm else None,
            "warm_p95": nearest_rank_p95(warm),
            "max": max(seconds) if seconds else None,
            "timeout_setting": runtime.RUNTIME_TIMEOUT,
        },
        "per_field": per_field,
    }


def _pct(value):
    return "n/a" if value is None else f"{value:.0%}"


def render_markdown(summary, results, run):
    lat = summary["latency_seconds"]
    lines = [
        "# Lab 13 receipt drafting evaluation",
        "",
        f"Generated by `CarCareLog/tools/evaluate_receipts.py` on {run['finished_utc']} (UTC).",
        "",
        "## Run",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Model tag | `{run['model']}` |",
        f"| Quantization | {run['runtime'].get('quantization_level')} |",
        f"| Parameters / family / format | {run['runtime'].get('parameter_size')} / "
        f"{run['runtime'].get('family')} / {run['runtime'].get('format')} |",
        f"| Weights digest matches pin `sha256-{runtime.PINNED_WEIGHTS_DIGEST}…` | "
        f"{'yes' if run['runtime'].get('weights_digest_matches_pin') else 'NO'} |",
        f"| Ollama version | {run['runtime'].get('ollama_version')} |",
        f"| Generation options | temperature {runtime.GENERATION_OPTIONS['temperature']}, "
        f"seed {runtime.GENERATION_OPTIONS['seed']}, JSON schema output |",
        f"| Machine | {run['machine']} |",
        f"| Python | {run['python']} |",
        f"| Samples | `CarCareLog/data/receipt-samples.jsonl` ({summary['receipts']} synthetic receipts) |",
        f"| Cold start | {'model unloaded before the first request' if run['cold_start'] else 'model may already be loaded'} |",
        "",
        "## Summary",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Receipts drafted / runtime failures | {summary['drafted']} / {summary['runtime_failures']} |",
        f"| Receipts with every field correct | {summary['receipts_all_fields_correct']} of {summary['drafted']} |",
        f"| Well-formed but wrong drafts (at least one wrong field) | {summary['well_formed_but_wrong_receipts']} |",
        f"| Field accuracy | {_pct(summary['field_accuracy'])} of {summary['field_values']} values |",
        f"| Wrong values flagged for the owner | {summary['wrong_values_flagged']} of {summary['wrong_values']}"
        f" ({_pct(summary['containment_catch_rate'])}) |",
        f"| **Wrong values shown as found (not flagged)** | **{summary['wrong_values_unflagged']}** |",
        f"| Correct values still flagged for a check | {summary['correct_values_flagged_for_check']} |",
        f"| First request (includes model load) | {lat['first_request']} s |",
        f"| Warm median / warm nearest-rank p95 / overall max | "
        f"{lat['warm_median']} s / {lat['warm_p95']} s / {lat['max']} s |",
        f"| Runtime timeout setting | {lat['timeout_setting']} s |",
        "",
        "Category is always flagged for a check by design, so its correct values count as correct_flagged.",
        "",
        "## Per field",
        "",
        "| Field | Accuracy | Correct | Correct, flagged | Wrong, flagged | Wrong, not flagged |",
        "|---|---|---|---|---|---|",
    ]
    for field, c in summary["per_field"].items():
        lines.append(f"| {field} | {_pct(c['accuracy'])} | {c['correct']} | {c['correct_flagged']} | "
                     f"{c['wrong_flagged']} | {c['wrong_unflagged']} |")
    lines += ["", "## Per receipt", "", "| Sample | Focus | Seconds | Wrong fields (got → label, page status) |",
              "|---|---|---|---|"]
    for r in results:
        if "fields" not in r:
            detail = f"runtime failure: {r['error']}"
        else:
            wrong = [f"{name}: {f['got']!r} → {f['want']!r} ({f['status']})"
                     for name, f in r["fields"].items() if f["outcome"].startswith("wrong")]
            detail = "; ".join(wrong) or "none"
        lines.append(f"| {r['id']} | {r['focus']} | {r['seconds']} | {detail} |")
    lines += ["", "## Reproduce", "",
              "```", "ollama pull " + runtime.PINNED_MODEL,
              "python CarCareLog/tools/evaluate_receipts.py", "```", ""]
    return "\n".join(lines)


def write_report(summary, results, run, output=OUTPUT):
    output.parent.mkdir(parents=True, exist_ok=True)
    output.with_suffix(".json").write_text(
        json.dumps({"run": run, "summary": summary, "results": results}, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(summary, results, run), encoding="utf-8")


def unload(model):
    try:
        runtime._call_runtime("POST", "/api/generate", {"model": model, "keep_alive": 0}, timeout=30)
    except Exception:  # noqa: BLE001 - unloading is best effort before a cold-start timing
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=runtime.PINNED_MODEL)
    parser.add_argument("--samples", type=Path, default=SAMPLES)
    parser.add_argument("--output", type=Path, default=OUTPUT, help="path without extension")
    parser.add_argument("--warm", action="store_true", help="do not unload the model first")
    args = parser.parse_args(argv)

    try:
        details = runtime.runtime_details(args.model)
    except runtime.ReceiptRuntimeUnavailable:
        sys.exit(f"Ollama is not reachable on 127.0.0.1:{runtime.RUNTIME_PORT}, or the model is missing.\n"
                 f"Start Ollama, then run: ollama pull {args.model}")
    if args.model != runtime.PINNED_MODEL or not details["weights_digest_matches_pin"]:
        print("Warning: this is not the pinned model build; results are not comparable.", file=sys.stderr)
    samples = load_samples(args.samples)
    if not args.warm:
        unload(args.model)
    started = datetime.now(timezone.utc)

    def drafter(text):
        return runtime.draft_receipt(text, args.model)

    results = []
    for index, sample in enumerate(samples, 1):
        results += evaluate([sample], drafter)
        print(f"[{index}/{len(samples)}] {sample['id']} {results[-1]['seconds']} s", flush=True)
    summary = summarize(results)
    run = {"model": args.model, "runtime": details, "cold_start": not args.warm,
           "started_utc": started.isoformat(timespec="seconds"),
           "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "machine": f"{platform.system()} {platform.release()} {platform.machine()} "
                      f"{platform.processor() or ''}".strip(),
           "python": platform.python_version()}
    write_report(summary, results, run, args.output)
    print(f"Field accuracy {_pct(summary['field_accuracy'])}; wrong values not flagged: "
          f"{summary['wrong_values_unflagged']}. Report: {args.output.with_suffix('.md')}")


if __name__ == "__main__":
    main()
