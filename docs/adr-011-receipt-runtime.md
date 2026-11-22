# ADR 011 Receipt Text Runtime

**Status:** Accepted. SA.A, the on-device runtime, is pinned to `qwen2.5:3b-instruct-q4_K_M` in Ollama 0.5.0 or later. Lab 13 adds the browser draft-review page, value checks, labeled samples, the evaluation tool and a paired comparison tool for SA.B (GPT-6.1 Sol).

The decision concerns where the receipt-text model executes for UC.1 and F.2.2.2. Both options produce an unconfirmed draft for review and leave the C.3 write boundary behind explicit owner confirmation. [Native alternatives](https://cloud.innoslate.com/cornell/p/746/diagrams/asset/318544).

## Decision

Use an on-device adapter (SA.A). Its application connection is loopback only. The operator starts Ollama, pulls the pinned model, and sets `CARCARE_OLLAMA_MODEL`; `CARCARE_OLLAMA_PORT` and `CARCARE_OLLAMA_TIMEOUT` (default 60 seconds) are optional. Leaving the model variable unset turns drafting off, and the page says so.

| Pinned item | Value |
| --- | --- |
| Model tag | `qwen2.5:3b-instruct-q4_K_M` (Qwen2.5 3B Instruct, Ollama library) |
| Quantization | Q4_K_M, GGUF, about 1.9 GB; weights digest starts with `sha256:5ee4f07cdb9b` |
| Runtime | Ollama 0.5.0 or later, for JSON-schema structured outputs |
| Generation | temperature 0, seed 18, `format` set to the draft JSON schema, keep-alive 30 minutes |
| License | Qwen Research License; acceptable for coursework, review before commercial use |

A 3B model at 4-bit quantization runs on an ordinary student laptop without a GPU, which keeps setup within the fifteen-minute local-setup allowance in the cost comparison. Larger local models remain an option if the evaluation shows the 3B model misses too many fields.

## How the draft flows

The browser posts pasted text to `POST /api/receipt-draft` (the internal adapter `POST /internal/v1/coordinate-ai` reaches the same handler). The adapter sends only the receipt text, inside a prompt that says the text is data, and asks for seven nullable fields. The model copies the odometer value and unit as printed; the application converts miles to kilometers. F.2.2.2 (`review_receipt_draft`) then validates each value on its own and looks it up in the receipt text:

- an invalid or future value becomes missing instead of failing the whole draft;
- a date, odometer reading, or shop name that is not printed is flagged for a check;
- a cost counts as found only when it is printed right after a total label, so a subtotal, a line item, or a total mentioned inside an injected instruction is flagged;
- an odometer reading without a unit, a service outside the fixed list, and every category are flagged for the owner.

The page fills the form, marks each field found, check, or missing, and saves only through the normal **Confirm & save** path. This pilot does not accept an image or perform OCR.

## Evidence

- `CarCareLog/tests/test_receipt_runtime.py`: request contents and pinned settings, draft handling, well-formed but wrong drafts, malformed replies, timeout, and the not-configured case.
- `CarCareLog/tests/test_receipt_review.py`: the value checks, including subtotal and injected-instruction cases.
- `CarCareLog/tools/smoke_test.py`: the primary use case end to end through a separate app process, with a stub runtime in CI or the real model with `--real-model`.
- `CarCareLog/tools/evaluate_receipts.py` on `CarCareLog/data/receipt-samples.jsonl`: field accuracy, wrong values flagged and not flagged, cold and warm latency, and the installed model build. The report goes to `docs/evidence/lab13-receipt-eval.md`.
- `CarCareLog/tools/compare_receipt_runtimes.py`: the same receipts through SA.A and SA.B, with token cost for SA.B. The report goes to `docs/evidence/lab13-receipt-comparison.md`.

## Comparison with SA.B

The comparison scores off-host request destinations, one-year incremental cost, manual continuity during model failure, field accuracy and response time. SA.B uses GPT-6.1 Sol as the hosted comparator.

`CarCareLog/tools/compare_receipt_runtimes.py` runs both candidates on the same 20 labeled synthetic receipts with the same prompt, schema and checks, and writes the side-by-side result to `docs/evidence/lab13-receipt-comparison.md`. SA.B is called only by that tool, with `store` false, and is not wired into the application. The hosted run needs an OpenAI API key and has not been done yet, so SA.B is scored at its best case.

With the team's swing weights and E5 scored from 1 at 2 s to 0 at the 60 s timeout, SA.A scores 0.867 on the Lab 13 evaluation. SA.B stays below 0.6 even with perfect accuracy and speed, because SA.A keeps receipt text on the owner's computer. Fifteen more minutes of local setup would put SA.A over the illustrative USD 80 budget, so setup time is tracked.

SA.B would require a vendor configuration, credentials, network policy, a policy-approved input subset, a retention review, and a throughput and outage benchmark. Its draft checks and confirmation controls would remain the same.

Sources: [Ollama generate contract](https://docs.ollama.com/api/generate), [Ollama structured outputs](https://ollama.com/blog/structured-outputs), [Ollama local-mode configuration](https://docs.ollama.com/faq), [qwen2.5 in the Ollama library](https://ollama.com/library/qwen2.5), [hosted GPT-6.1 Sol pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
