# CarCareLog

Cornell SYSEN 5151 · Team 18 · Implementation and integration

CarCareLog keeps a vehicle's confirmed service history, costs, and maintenance reminders together. The primary use case is **UC.1 Manage Maintenance Records**. The owner can paste receipt text or select a JPEG/PNG photo. The local model drafts a record. The application compares text-derived values with the source text and flags image-derived values for visual review. Nothing is saved until the owner selects **Confirm & save**.

## Pinned versions

| Component | Pinned version | Notes |
| --- | --- | --- |
| Python | 3.10 or later | CI runs 3.12 on Ubuntu, Windows, and macOS, plus 3.10, 3.11, and 3.13 on Ubuntu. |
| Python packages | None | Standard library only, including SQLite. There is nothing to `pip install`. |
| Model runtime | Ollama with Qwen3.5 vision support | Use a current Ollama release that supports this model and JSON-schema outputs. The app talks to it only on `127.0.0.1`. |
| Language model | `qwen3.5:4b` | Qwen3.5 4B from the [Ollama library](https://ollama.com/library/qwen3.5:4b), with image and text input. |
| Quantization | Q4_K_M (4-bit, GGUF) | The GGUF weights start with `sha256:a9d0a3e1d8c9` and the vision projector with `sha256:e56a899b1540`. |
| Generation settings | temperature 0, seed 18, thinking off, JSON schema output | Set in [`receipt_runtime.py`](CarCareLog/backend/receipt_runtime.py). Keep-alive 30 minutes. |
| Request timeout | 60 seconds | Set `CARCARE_OLLAMA_TIMEOUT` to change it. |
| Model license | Apache 2.0 | See the license supplied with the model. |

The model tag, quantization, and digest are checked and written into every evaluation report, so a different build is easy to spot.

## Run the application

From the repository root, start the app with a fresh temporary database.

Windows PowerShell:

```powershell
$env:CARCARE_DB = Join-Path ([System.IO.Path]::GetTempPath()) ("CarCareLog-demo-" + [guid]::NewGuid() + ".db")
$env:CARCARE_PORT = '8000'
$env:CARCARE_OLLAMA_MODEL = 'qwen3.5:4b'
py -3 CarCareLog/backend/app.py
```

macOS or Linux:

```bash
CARCARE_DB="$(mktemp)" CARCARE_OLLAMA_MODEL=qwen3.5:4b python3 CarCareLog/backend/app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop the server with Ctrl+C.

To run without AI drafting, leave `CARCARE_OLLAMA_MODEL` unset (`Remove-Item Env:CARCARE_OLLAMA_MODEL` in PowerShell). Manual entry works the same either way. For a persistent workspace, omit the `CARCARE_DB` override; records are then saved in `CarCareLog/data/carcare.db`. If port 8000 is in use, set `CARCARE_PORT` to a free port.

## Turn on the local model

1. Install a current version of Ollama from [ollama.com/download](https://ollama.com/download) and make sure it is running.
2. Download the pinned model: `ollama pull qwen3.5:4b`
3. Check the build: `ollama show qwen3.5:4b` should list quantization `Q4_K_M` and approximately 4B parameters and vision support.
4. Start the app with `CARCARE_OLLAMA_MODEL` set as shown above.

The model runs on the same computer. The app sends the supplied receipt text or image only to loopback Ollama. It does not send vehicle names or stored history to the model and never writes the uploaded photo to its database. The first draft after startup loads the model into memory and takes longer than later drafts.

## Demonstration script

This walks the primary use case end to end: receipt text (the query) → the selected vehicle's record store (the data source) → the local language model → the application API → the web page.

1. Start the app with the local model turned on, open the page, and select **Load demo data**. The demo vehicle shows 3 records and a total of $359.99.
2. Select **Add record**, open **Draft from a receipt**, and select **Use sample receipt**. You can instead leave the text empty and choose one JPEG or PNG up to 4 MiB. The photo appears alongside the draft, and every proposed photo-derived field requires a visual check. The sample text is a QuickLube Express oil change on 11/16/2026 at 32,311 mi with a $89.99 total after tax. The same text is in [`demo-receipt.txt`](CarCareLog/data/demo-receipt.txt).
3. Select **Draft with local AI**. The page sends the text to `POST /api/receipt-draft`. The service calls the model, converts 32,311 mi to 52,000 km, and checks every value against the receipt.
4. Review the draft. Each field shows whether its value was found on the receipt (✓), needs a check (amber), or is missing (red). Category is always left for the owner to confirm. The banner says the draft is not saved yet.
5. Change anything that is wrong, then select **Confirm & save**. The timeline gains one row and the total becomes $449.98.
6. Refresh the page to show that the record was saved.
7. Fallback: stop Ollama (or start the app with `CARCARE_OLLAMA_PORT` set to an unused port) and select **Draft with local AI** again. The page says the AI draft is unavailable, the form is unchanged, and a manual entry still saves.

Use a fresh temporary database for each rehearsal. Keep real vehicle records off a shared screen.

## Reproduce on a clean machine

You need Git and Python 3.10 or later. Ollama is needed only for the real-model steps.

```bash
git clone https://github.com/sysen5151-fall2026/CarCareLog-T18.git
cd CarCareLog-T18/CarCareLog
python3 -m unittest discover -s tests -v                # all tests, no model needed
cd ..
python3 CarCareLog/tools/smoke_test.py                  # primary use case end to end, stub runtime
ollama pull qwen3.5:4b
python3 CarCareLog/tools/smoke_test.py --real-model     # same walk-through with the pinned model
python3 CarCareLog/tools/evaluate_receipts.py           # labeled-receipt evaluation report
```

On Windows, use `py -3` in place of `python3`.

The smoke test starts the real application as a separate process on a free port with a temporary database. It loads the demo data, drafts the sample receipt, checks that the draft wrote nothing, saves it with owner confirmation, checks the dashboard and a repeated submit, restarts the app to check persistence, and finally checks the R2 fallback with the runtime unavailable. Without `--real-model`, a small stub answers in place of Ollama, so the check runs anywhere, including CI. The record of our clean-machine run is in [`docs/clean-machine-run.md`](docs/clean-machine-run.md).

## Model evaluation

[`receipt-samples.jsonl`](CarCareLog/data/receipt-samples.jsonl) holds 20 synthetic, labeled receipts. They cover miles and kilometers, a missing date, odometer, or shop name, subtotal and tax lines, discounts, cash and change, two dates, services outside the fixed list, and a line that tries to instruct the model. Each sample has the expected saved record and the ideal model draft.

[`evaluate_receipts.py`](CarCareLog/tools/evaluate_receipts.py) runs every sample through the same adapter and checks as the web page. It unloads the model first so the first request measures a cold start. For each field it reports whether the value was correct and whether a wrong value was flagged for the owner or shown as found. It also reports latency and the model build. The report is written to `docs/evidence/qwen35-text-eval.md` and `.json`.

The following links preserve the earlier Qwen2.5 text run: [Lab 13 results](docs/evidence/lab13-receipt-eval.md) and [per-receipt JSON](docs/evidence/lab13-receipt-eval.json) for the measured Windows run.

[`compare_receipt_runtimes.py`](CarCareLog/tools/compare_receipt_runtimes.py) reproduces the two historical text alternatives from ADR 011 on the same 20 synthetic receipts, with the same prompt, draft schema and checks: SA.A, the historical Qwen2.5 3B Instruct in Ollama, and SA.B, the hosted comparator `gpt-6.1-sol` called through the OpenAI Responses API (`https://api.openai.com/v1/responses`, reasoning effort low, `store` false). The hosted model is used only by this tool; the web application never sends receipt text off the computer. On Windows:

```powershell
py -3 CarCareLog/tools/compare_receipt_runtimes.py local
py -3 CarCareLog/tools/compare_receipt_runtimes.py hosted --prompt-key   # type the OpenAI API key at the hidden prompt
py -3 CarCareLog/tools/compare_receipt_runtimes.py report
```

The first two commands write `docs/evidence/lab13-receipt-comparison-local.json` and `-hosted.json`; `report` writes the side-by-side [`lab13-receipt-comparison.md`](docs/evidence/lab13-receipt-comparison.md) with accuracy, wrong values shown as found, latency, and the hosted token cost. The key is read without being shown or saved; `OPENAI_API_KEY` also works. Use `python3` on macOS or Linux.

The checks catch values that are well formed but not on the receipt: a date or odometer reading that is not printed, a cost that is not printed next to the total (for example a subtotal), a shop name that is not printed, and miles entered without a unit. A value that is printed on the receipt but belongs to the wrong field can still pass, which is why the owner reviews every field before saving.

## OpsCon and as-built system

Open [T18 Universe Context](https://cloud.innoslate.com/cornell/p/746/diagrams/asset/184237). The chart marks the four asset nodes by implementation status.

| OpsCon asset | Status | Location in this build |
| --- | --- | --- |
| Ext.1 Vehicle Owner | Working | The [web interface](CarCareLog/frontend/index.html) and [browser interactions](CarCareLog/frontend/app.js) support manual entry and receipt text or image drafting with review. |
| C.0 CarCareLog System | Partial | C.1 is the browser UI. C.2 is the [HTTP service](CarCareLog/backend/app.py) with [F.2.2 coordination](CarCareLog/backend/function_f22.py), including the F.2.2.2 draft checks. C.3 is the SQLite store. Owner authentication and data isolation remain open. |
| Ext.2 AI Model Runtime | Working locally | The [runtime adapter](CarCareLog/backend/receipt_runtime.py) calls the pinned model in a local Ollama service. The local adapter supports JPEG/PNG and pasted text. General questions and hosted product operation remain open. |
| Ext.3 Application Operator | Partial | The operator sets the model, runtime port, and timeout with environment variables and starts and stops the app from a terminal. A dedicated operator interface and automated recovery are pending. |

The service provider gives receipts to the owner outside the application. There is no direct service-provider integration.

## Use-case coverage

| Use case | Current build |
| --- | --- |
| UC.1 Maintenance records | Manual create, edit, delete, search, CSV export, and explicit confirmation. Text and image drafting with the local model, per-field checks, and owner review before saving. |
| UC.2 Maintenance reminders | A rule uses a source reference and a mileage or calendar interval. The separate warning window is 500 international miles (804.672 km) or 30 days from a due limit. |
| UC.3 Maintenance expenses | The dashboard shows recorded total and monthly costs based on confirmed service records. |
| UC.4 Record questions | Two predefined lookups return the last oil change or total cost with source record IDs. General questions and answers grounded in a vehicle manual remain open. |

## Design decisions and risks

[ADR 011](docs/adr-011-receipt-runtime.md) records the original choice of SA.A and Qwen2.5. [ADR 012](docs/adr-012-local-receipt-vision.md) records the Qwen3.5 image-input increment. The [risk register](docs/risks.md) links to the native Innoslate matrix. Open items are tracked in [GitHub Issues](https://github.com/sysen5151-fall2026/CarCareLog-T18/issues).

## Tests and related files

- [Interface contract](contracts/api-v1.yaml), [route table](docs/route-table.md), and [traceability](docs/traceability.md)
- [Receipt runtime tests](CarCareLog/tests/test_receipt_runtime.py), [draft check tests](CarCareLog/tests/test_receipt_review.py), [evaluation tests](CarCareLog/tests/test_receipt_evaluation.py), and [requirement coverage](CarCareLog/docs/MVP_SCOPE.md)
- [Chapter 10 simulation evidence](docs/modeling-and-simulation.md) and [historical Milestone 2 demo](docs/DEMO_RELEASE.md)

From `CarCareLog/`, run `py -3 -m unittest discover -s tests -v` on Windows or `python3 -m unittest discover -s tests -v` on macOS or Linux. The tests use temporary databases and a loopback stand-in for the model runtime. They check the application's handling of drafts, failures, and timeouts. Model accuracy and latency come from the evaluation tool, not from the unit tests.
