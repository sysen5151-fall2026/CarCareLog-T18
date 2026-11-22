"""Compare the pinned local and hosted models on the Lab 13 labeled receipt set.

    py -3 CarCareLog/tools/compare_receipt_runtimes.py local
    py -3 CarCareLog/tools/compare_receipt_runtimes.py hosted --prompt-key
    py -3 CarCareLog/tools/compare_receipt_runtimes.py report

`local` runs qwen2.5:3b-instruct-q4_K_M in Ollama on this computer. `hosted` runs
GPT-6.1 Sol through the OpenAI Responses API; it is a comparison only and is not
wired into the web application. Both use the same prompt, draft schema and F.2.2.2
checks, and only the synthetic receipts leave the computer. `report` writes the
side-by-side Markdown from the two JSON result files.
"""

import argparse
from datetime import datetime, timezone
from getpass import getpass
import hashlib
import json
import os
from pathlib import Path
import statistics
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from evaluate_receipts import FIELDS, SAMPLES, evaluate, load_samples, nearest_rank_p95, runtime, summarize, unload


HOSTED_MODEL = "gpt-6.1-sol"
HOSTED_ENDPOINT = "https://api.openai.com/v1/responses"
# Standard processing list price per million tokens, OpenAI model page, November 2026.
# Reasoning tokens are billed as output tokens.
HOSTED_PRICE_PER_MILLION = {"input": 2.00, "output": 10.00}
OUTPUT = Path(__file__).resolve().parents[2] / "docs/evidence/lab13-receipt-comparison"
DEADLINE = 60
# Reasoning tokens count against this limit, so leave room beyond the short JSON answer.
MAX_OUTPUT_TOKENS = 2048
STOP_ON_FIRST = {400, 401, 403, 404, 429}


class HostedStop(SystemExit):
    pass


def hosted_schema():
    schema = json.loads(json.dumps(runtime.DRAFT_SCHEMA))
    for field in ("service_item", "category", "odometer_unit"):
        schema["properties"][field]["type"] = ["string", "null"]
    return schema


def hosted_payload(receipt_text):
    return {
        "model": HOSTED_MODEL,
        "input": runtime.build_request(receipt_text, HOSTED_MODEL)["prompt"],
        "store": False,
        "reasoning": {"effort": "low"},
        "max_output_tokens": MAX_OUTPUT_TOKENS,
        "text": {"format": {"type": "json_schema", "name": "receipt_draft",
                            "schema": hosted_schema(), "strict": True}},
    }


def parse_hosted(result):
    if result.get("status") == "incomplete":
        reason = (result.get("incomplete_details") or {}).get("reason", "unknown")
        raise runtime.ReceiptRuntimeUnavailable(f"Hosted response incomplete ({reason}).")
    content = [part.get("text", "") for item in result.get("output", [])
               for part in item.get("content", []) or [] if part.get("type") == "output_text"]
    try:
        draft = json.loads("".join(content))
    except ValueError as exc:
        raise runtime.ReceiptRuntimeUnavailable("Hosted runtime returned no usable draft.") from exc
    if not isinstance(draft, dict) or set(draft) != set(runtime.DRAFT_FIELDS):
        raise runtime.ReceiptRuntimeUnavailable("Hosted draft did not match the contract.")
    return draft


def hosted_drafter(key, opener=urlopen):
    usage = []

    def draft(receipt_text):
        request = Request(HOSTED_ENDPOINT, data=json.dumps(hosted_payload(receipt_text)).encode(), method="POST",
                          headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        try:
            with opener(request, timeout=DEADLINE) as response:
                result = json.load(response)
        except HTTPError as exc:
            usage.append(None)
            raise runtime.ReceiptRuntimeUnavailable(f"Hosted runtime HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, ValueError, TypeError, KeyError, OSError) as exc:
            usage.append(None)
            raise runtime.ReceiptRuntimeUnavailable("Hosted runtime returned no usable draft.") from exc
        tokens = result.get("usage") or {}
        usage.append({"input_tokens": tokens.get("input_tokens", 0),
                      "output_tokens": tokens.get("output_tokens", 0),
                      "reasoning_tokens": (tokens.get("output_tokens_details") or {}).get("reasoning_tokens", 0)})
        return parse_hosted(result)

    draft.usage = usage
    return draft


def hosted_cost(usage):
    rows = [u for u in usage if u]
    tokens = {name: sum(u[name] for u in rows) for name in ("input_tokens", "output_tokens", "reasoning_tokens")}
    dollars = (tokens["input_tokens"] * HOSTED_PRICE_PER_MILLION["input"]
               + tokens["output_tokens"] * HOSTED_PRICE_PER_MILLION["output"]) / 1_000_000
    return {**tokens, "estimated_usd": round(dollars, 4),
            "estimated_usd_per_draft": round(dollars / len(rows), 5) if rows else None,
            "price_per_million": HOSTED_PRICE_PER_MILLION}


def e5_value(p95):
    """E5 value: 1 at 2 s or faster, 0 at the 60 s adapter timeout, linear in between."""
    if p95 is None:
        return None
    if p95 <= 2:
        return 1.0
    if p95 >= DEADLINE:
        return 0.0
    return (DEADLINE - p95) / (DEADLINE - 2)


def measure(samples, drafter):
    results = []
    for sample in samples:
        entry = evaluate([sample], drafter)[0]
        usage = getattr(drafter, "usage", None)
        if usage:
            entry["usage"] = usage[-1]
        code = entry.get("error", "") or ""
        if not results and any(code == f"Hosted runtime HTTP {status}." for status in STOP_ON_FIRST):
            raise HostedStop(f"{code} Check the API key, model access and rate limit, then rerun.")
        results.append(entry)
        print(f"{entry['id']} {entry['seconds']:.3f} s" + (f" ({entry['error']})" if entry["error"] else ""), flush=True)
    completed = [row for row in results if "fields" in row]
    durations = [row["seconds"] for row in results[1:] if "fields" in row]
    correct = sum(field["outcome"].startswith("correct") for row in completed for field in row["fields"].values())
    p95 = nearest_rank_p95(durations)
    expected = len(samples) * len(FIELDS)
    summary = summarize(results)
    return {
        "first_request_seconds": results[0]["seconds"],
        "requests": len(samples), "completed": len(completed),
        "failures": len(samples) - len(completed),
        "expected_fields": expected, "correct_fields": correct,
        "field_accuracy": correct / expected,
        "receipts_all_fields_correct": summary["receipts_all_fields_correct"],
        "wrong_values_flagged": summary["wrong_values_flagged"],
        "wrong_values_unflagged": summary["wrong_values_unflagged"],
        "correct_values_flagged_for_check": summary["correct_values_flagged_for_check"],
        "per_field_accuracy": {f: summary["per_field"][f]["accuracy"] for f in FIELDS},
        "warm_median_seconds": statistics.median(durations) if durations else None,
        "warm_p95_seconds": p95,
        "v5": e5_value(p95),
        "review_seconds_included": False,
        "results": results,
    }


def samples_digest(path=SAMPLES):
    """SHA-256 of the sample file with line endings normalized, so Windows and Linux checkouts agree."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def result_path(provider, output=OUTPUT):
    return output.with_name(output.name + "-" + provider).with_suffix(".json")


def _seconds(value):
    return "n/a" if value is None else f"{value:.2f} s"


def _wrong(row):
    if "fields" not in row:
        return f"failed: {row.get('error')}"
    wrong = [f"{name} {f['got']!r} ({f['status']})" for name, f in row["fields"].items()
             if f["outcome"].startswith("wrong")]
    return "; ".join(wrong) or "all correct"


def render_report(local, hosted):
    cost = hosted.get("cost") or {}
    lines = [
        "# Lab 13 receipt runtime comparison",
        "",
        "Both runtimes drafted the same 20 synthetic receipts with the same prompt, draft schema and F.2.2.2 checks. "
        "The local runtime is the one the web application uses. The hosted runtime was called only by "
        "`CarCareLog/tools/compare_receipt_runtimes.py`, with `store` set to false, and is not wired into the application.",
        "",
        "| | Local (SA.A) | Hosted (SA.B) |",
        "|---|---|---|",
        f"| Model | `{runtime.PINNED_MODEL}` in Ollama {local.get('ollama_version')} | `{hosted.get('model')}`, reasoning effort "
        f"{hosted.get('reasoning_effort')} |",
        f"| Where it ran | This computer, loopback only | {hosted.get('endpoint')} |",
        f"| Run (UTC) | {local.get('started_utc')} | {hosted.get('started_utc')} |",
        f"| Samples SHA-256 | `{local.get('samples_sha256', '')[:12]}…` | `{hosted.get('samples_sha256', '')[:12]}…` |",
        f"| Drafts completed | {local['completed']} of {local['requests']} | {hosted['completed']} of {hosted['requests']} |",
        f"| Field accuracy | {local['field_accuracy']:.0%} ({local['correct_fields']} of {local['expected_fields']}) | "
        f"{hosted['field_accuracy']:.0%} ({hosted['correct_fields']} of {hosted['expected_fields']}) |",
        f"| Receipts with every field correct | {local.get('receipts_all_fields_correct')} | "
        f"{hosted.get('receipts_all_fields_correct')} |",
        f"| Wrong values flagged for the owner | {local.get('wrong_values_flagged')} | {hosted.get('wrong_values_flagged')} |",
        f"| **Wrong values shown as found** | **{local.get('wrong_values_unflagged')}** | "
        f"**{hosted.get('wrong_values_unflagged')}** |",
        f"| First request | {_seconds(local['first_request_seconds'])} (cold model load) | "
        f"{_seconds(hosted['first_request_seconds'])} |",
        f"| Warm median / nearest-rank p95 | {_seconds(local['warm_median_seconds'])} / {_seconds(local['warm_p95_seconds'])} | "
        f"{_seconds(hosted['warm_median_seconds'])} / {_seconds(hosted['warm_p95_seconds'])} |",
        f"| E5 value, 1 at 2 s to 0 at the 60 s timeout | {e5_value(local['warm_p95_seconds']):.2f} | "
        f"{e5_value(hosted['warm_p95_seconds']):.2f} |",
        f"| Model cost for this run | $0 (local electricity not counted) | about ${cost.get('estimated_usd', 0):.4f} "
        f"({cost.get('input_tokens', 0)} input, {cost.get('output_tokens', 0)} output tokens, "
        f"{cost.get('reasoning_tokens', 0)} of them reasoning) |",
        "",
        "Hosted cost uses the standard list price of $2 per million input tokens and $10 per million output tokens. "
        "Latency excludes the owner's review time. Category is always flagged by design.",
        "",
        "## Per field accuracy",
        "",
        "| Field | Local | Hosted |",
        "|---|---|---|",
    ]
    for field in FIELDS:
        lines.append(f"| {field} | {local['per_field_accuracy'][field]:.0%} | {hosted['per_field_accuracy'][field]:.0%} |")
    lines += ["", "## Per receipt", "", "| Sample | Focus | Local wrong values (page status) | Hosted wrong values (page status) |",
              "|---|---|---|---|"]
    hosted_rows = {row["id"]: row for row in hosted["results"]}
    for row in local["results"]:
        lines.append(f"| {row['id']} | {row['focus']} | {_wrong(row)} | {_wrong(hosted_rows[row['id']])} |")
    lines += ["", "## Reproduce", "", "```",
              "ollama pull " + runtime.PINNED_MODEL,
              "py -3 CarCareLog/tools/compare_receipt_runtimes.py local",
              "py -3 CarCareLog/tools/compare_receipt_runtimes.py hosted --prompt-key",
              "py -3 CarCareLog/tools/compare_receipt_runtimes.py report", "```", ""]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("provider", choices=["local", "hosted", "report"])
    parser.add_argument("--prompt-key", action="store_true",
                        help="Read the hosted API key without displaying or saving it.")
    args = parser.parse_args(argv)
    if args.provider == "report":
        local, hosted = (json.loads(result_path(name).read_text(encoding="utf-8")) for name in ("local", "hosted"))
        if local.get("samples_sha256") != hosted.get("samples_sha256"):
            raise SystemExit("The two runs used different sample files; rerun both.")
        target = OUTPUT.with_suffix(".md")
        target.write_text(render_report(local, hosted), encoding="utf-8")
        print(target)
        return
    samples = load_samples()
    if args.provider == "hosted":
        key = (getpass("OpenAI API key: ") if args.prompt_key else os.environ.get("OPENAI_API_KEY", "")).strip()
        if not key:
            raise SystemExit("No API key was provided. Use --prompt-key or set OPENAI_API_KEY.")
        run = {"model": HOSTED_MODEL, "endpoint": HOSTED_ENDPOINT, "reasoning_effort": "low",
               "max_output_tokens": MAX_OUTPUT_TOKENS, "store": False}
        drafter = hosted_drafter(key)
    else:
        try:
            run = runtime.runtime_details(runtime.PINNED_MODEL)
        except runtime.ReceiptRuntimeUnavailable:
            raise SystemExit(f"Ollama is not reachable or the model is missing. Run: ollama pull {runtime.PINNED_MODEL}")
        if not run["weights_digest_matches_pin"]:
            raise SystemExit("The installed local weights do not match the pinned digest.")
        run["model"] = runtime.PINNED_MODEL
        unload(runtime.PINNED_MODEL)

        def drafter(text):
            return runtime.draft_receipt(text, runtime.PINNED_MODEL)

    run["provider"] = args.provider
    run["samples"] = SAMPLES.name
    run["samples_sha256"] = samples_digest()
    run["started_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run.update(measure(samples, drafter))
    if args.provider == "hosted":
        run["cost"] = hosted_cost(drafter.usage)
    run["completed_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    target = result_path(args.provider)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
