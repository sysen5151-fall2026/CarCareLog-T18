# CarCareLog

Cornell SYSEN 5151 · Team 18 · Implementation and integration

CarCareLog keeps a vehicle's confirmed service history, costs, and maintenance reminders together. The primary use case is **UC.1 Manage Maintenance Records**. The owner can paste receipt text or select a JPEG/PNG photo. The local model drafts a record. The application compares text-derived values with the source text and flags image-derived values for visual review. Nothing is saved until the owner selects **Confirm & save**.

## Quick start for poster visitors

1. [Download the classroom build as a ZIP](https://github.com/sysen5151-fall2026/CarCareLog-T18/archive/refs/heads/final-poster-demo.zip) and extract it. Open a terminal in the extracted folder containing `run_demo.py`. You need [Python 3.10 or later](https://www.python.org/downloads/). The core workflow uses the Python standard library. To import PDF manuals, install the pinned reader with `python -m pip install -r CarCareLog/requirements-manual-pdf.txt` using the same Python as the launcher.
2. Start the app with the command for your computer.

   | Windows PowerShell | macOS or Linux terminal |
   | --- | --- |
   | `python run_demo.py` | `python3 run_demo.py` |

   On Windows installations that expose the Python launcher instead of `python`, use `py -3 run_demo.py`.

3. Open [http://127.0.0.1:8000](http://127.0.0.1:8000) on the same computer. Select **Load demo data** to see a vehicle with three service records totaling **$359.99**. Try **Add record**, enter a service manually, select **Confirm & save**, then refresh the page to see the saved record. Stop the app with **Ctrl+C** in the terminal.

To try **separate local accounts**, add `--accounts` to your start command. Register a demo username and password in the browser. Each account has its own vehicle history on this computer. The single-owner and account modes store their records separately under `.carcarelog-classroom` in your home folder. A new run reopens the same records. To use an empty classroom workspace, add `--data-dir` followed by the path to a new folder.

To try **AI drafting from a receipt photo or text**, install and start [Ollama](https://ollama.com/download), then run `ollama pull qwen3.5:4b` once. Restart the app with `--ai` added to the same command (the flags `--ai --accounts` also work together). In **Add record**, open **Draft from a receipt**, select **Use sample receipt** or choose a JPEG/PNG, then select **Draft with local AI**. Review the fields before saving. If port 8000 is busy, add `--port 8001` and use the address printed in the terminal.

The ZIP includes a [synthetic oil-change receipt](CarCareLog/data/demo-receipt.png) for the image workflow. Choose that file from the extracted `CarCareLog/data` folder. The printed total is $43.19 after a $10 coupon. The [product replay](docs/evidence/local-poster-image-smoke.json) records the draft, owner confirmation and saved record after restart. The [local account check](docs/evidence/local-owner-demo-2026-11-23.md) documents signup, sign-in and separate histories.

**Try a phone calendar reminder.** Load the demo data, find **Tire rotation** in **Maintenance reminders** and choose **Save to calendar (.ics)**. Transfer the file to your phone, open it in a calendar that supports iCalendar import, and check the event and its alert before saving. A future service date exports at 09:00 in the calendar's local time, with a display alert one day earlier. For a service due tomorrow, the alert is at 09:00 on the due date. Mileage-only, already-due and missing-history rules remain on the dashboard. The file is a snapshot. Replace it in your calendar if your service date changes.

**Try a vehicle manual.** In Maintenance reminders, import a text-based PDF, paste manual text, or select an approved publisher URL. A direct [Tesla tire-rotation page](https://service.tesla.com/docs/Public/diy/model3/en_us/GUID-A84FDD77-7A8C-42F6-9385-E3F9CEE245A4.html) is available for a Model 3 example. Check that the document matches the vehicle and read its conditions before confirming an interval. A local file is labeled owner-supplied. The [publisher checks](docs/evidence/manual-publisher-validation.json) include a Toyota guide whose table produced no automatic suggestion.

**Ask about this vehicle.** In the history panel, type a question such as “Which repair had the highest invoice?” or ask about the tire rotation interval in an imported manual. Follow the record link or inspect the quoted passage. Unsupported questions, uncertain allocations and missing sources are identified in the response.

**Restore a workspace.** The standard launcher automatically snapshots SQLite while it is running. On restart it checks for damage and can restore from a verified local snapshot. See the [operator instructions and measured recovery times](docs/verification/storage-recovery.md).

## Pinned versions

The final report compares deployment options at the architecture level. Local inference keeps receipts on the owner's device and works offline once the weights are installed; the owner supplies adequate memory and compute. Hosted inference offloads model execution to the provider and requires network access, credentials, a policy for sending receipts and a plan for usage charges. Local receipt accuracy and latency are measured. Hosted performance and cost per receipt were not measured.

During the [two-hour local dashboard check](docs/evidence/two-hour-local-availability.json), 55 of 121 scheduled reads ran. All 55 returned the expected vehicle, three receipts and the correct total. The collector missed 66 slots. Monitoring resumed on the same fixture after a service restart. Service availability during the gaps is unknown.

The [earlier two-minute check](docs/evidence/short-local-availability.json) recorded three successful reads and a separate planned restart. The [seven-day observation](docs/verification/seven-day-core-availability.md) remains an optional follow-up. Its 99% availability target has not been measured.

| Component | Pinned version | Notes |
| --- | --- | --- |
| Python | 3.10 or later | CI runs 3.12 on Ubuntu, Windows, and macOS, plus 3.10, 3.11, and 3.13 on Ubuntu. |
| Optional PDF dependency | See [pinned reader](CarCareLog/requirements-manual-pdf.txt) | Text and approved publisher HTML import, history lookup and SQLite recovery use the standard library. |
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

The owner selects a vehicle, reviews a local draft, and confirms a service record. The model receives only the supplied receipt. SQLite receives the reviewed record when the owner confirms.

1. Start the app with the local model turned on, open the page, and select **Load demo data**. The demo vehicle shows 3 records and a total of $359.99.
2. Select **Add record**, open **Draft from a receipt**, and select **Use sample receipt**. You can instead leave the text empty and choose one JPEG or PNG up to 4 MiB. The photo appears alongside the draft, and every proposed photo-derived field requires a visual check. The sample text is a QuickLube Express oil change on 11/16/2026 at 32,311 mi with a $89.99 total after tax. The same text is in [`demo-receipt.txt`](CarCareLog/data/demo-receipt.txt).
3. Select **Draft with local AI**. The page sends the text to `POST /api/receipt-draft`. The service calls the model, converts 32,311 mi to 52,000 km, and checks every value against the receipt.
4. Review the draft. Each field shows whether its value was found on the receipt (✓), needs a check (amber), or is missing (red). Category is always left for the owner to confirm. The banner says the draft is not saved yet.
5. Change anything that is wrong, then select **Confirm & save**. The timeline gains one row and the total becomes $449.98.
6. Refresh the page to show that the record was saved.
7. Fallback: stop Ollama (or start the app with `CARCARE_OLLAMA_PORT` set to an unused port) and select **Draft with local AI** again. The page says the AI draft is unavailable, the form is unchanged, and a manual entry still saves.

To try a combined invoice, enter a single $180 total and select both Oil change and Tire rotation. After confirmation, the vehicle has one more record, the total rises by $180, and configured intervals for both services use the new entry. Enter the same date, shop and total in another new record to see the duplicate warning. Review the existing record before deciding whether the second receipt is a separate purchase.

Use a fresh temporary database for each rehearsal. Keep real vehicle records off a shared screen.

## Reproduce on a clean machine

You need Git and Python 3.10 or later. Ollama is needed only for the real-model steps.

```bash
git clone --branch final-poster-demo https://github.com/sysen5151-fall2026/CarCareLog-T18.git
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

The [November 22 image baseline](docs/evidence/chapter14-qwen35-receipt-images.md) measured 120/120 fields on 20 clean synthetic images before multi-service extraction was added. Those measurements cover the original six fields. The [first-time-owner protocol](docs/verification/receipt-owner-study.md) measures a different outcome: whether a driver can accurately save a photographed receipt in 180 seconds. The earlier Qwen2.5 text results are in the [Lab 13 report](docs/evidence/lab13-receipt-eval.md) and [per-receipt JSON](docs/evidence/lab13-receipt-eval.json).

[`compare_receipt_runtimes.py`](CarCareLog/tools/compare_receipt_runtimes.py) can compare the two text alternatives from ADR 011 on the 20 synthetic receipts. SA.A uses Qwen2.5 3B Instruct in Ollama and SA.B uses the hosted `gpt-6.1-sol` comparator. To reproduce the historical configuration, check out its recorded revision so the prompt and schema match. The optional comparison tool sends input to the selected runtime. The web application keeps receipts on the local computer. On Windows:

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
| C.0 CarCareLog System | Partial | C.1 is the browser UI. C.2 is the [HTTP service](CarCareLog/backend/app.py) with [F.2.2 coordination](CarCareLog/backend/function_f22.py). C.3 stores confirmed records in SQLite. The [optional local account service](CarCareLog/backend/owner_site.py) signs owners in and gives each account a separate ledger on the same device. |
| Ext.2 AI Model Runtime | Working locally | The [runtime adapter](CarCareLog/backend/receipt_runtime.py) calls the pinned model in a local Ollama service. The local adapter supports JPEG/PNG and pasted text. Typed vehicle questions use local retrieval and verified record arithmetic. Optional loopback keyword expansion receives only the question. The product runs locally. |
| Ext.3 Application Operator | Partial | The operator sets the model, runtime port, and timeout with environment variables and starts and stops the app from a terminal. Startup integrity checks and automatic snapshots cover local recovery. Operators use the documented CLI. |

The service provider gives receipts to the owner outside the application. There is no direct service-provider integration.

## Use-case coverage

| Use case | Current build |
| --- | --- |
| UC.1 Maintenance records | Create, edit, delete, search or export confirmed records. A new record can contain several services on one receipt. A new save checks for an existing entry with the same vehicle, date, shop and total. Changing a receipt source invalidates its AI draft. |
| UC.2 Maintenance reminders | An owner can enter an interval directly or import a manual and confirm a source-linked suggestion. The dashboard warning window is 500 international miles (804.672 km) or 30 days. A future dated service can also be exported to the owner's calendar with a local alert. |
| UC.3 Maintenance expenses | Each confirmed receipt contributes its total once to recorded spending and the monthly chart. Its category applies to the whole receipt. |
| UC.4 Record questions | Four history lookups cover total spending, last oil change, last tire-rotation mileage and brake spending for the year. Use a source link to open its record. A mixed-service receipt without item prices is identified separately in brake-spending answers. Typed queries can also search vehicle records or quote an imported manual; weak matches are labeled and missing evidence is reported. |

## Design decisions and risks

[ADR 011](docs/adr-011-receipt-runtime.md) records the original choice of SA.A and Qwen2.5. [ADR 012](docs/adr-012-local-receipt-vision.md) records the Qwen3.5 image-input increment. [ADR 013](docs/adr-013-local-owner-accounts.md) documents account sign-in and separate ledgers for a classroom computer. The [risk register](docs/risks.md) links to the native Innoslate matrix. Open items are tracked in [GitHub Issues](https://github.com/sysen5151-fall2026/CarCareLog-T18/issues).

## Tests and related files

- [Interface contract](contracts/api-v1.yaml), [route table](docs/route-table.md), and [traceability](docs/traceability.md)
- [Receipt runtime tests](CarCareLog/tests/test_receipt_runtime.py), [draft check tests](CarCareLog/tests/test_receipt_review.py), [evaluation tests](CarCareLog/tests/test_receipt_evaluation.py), and [requirement coverage](CarCareLog/docs/MVP_SCOPE.md)
- [Chapter 10 simulation evidence](docs/modeling-and-simulation.md) and [historical Milestone 2 demo](docs/DEMO_RELEASE.md)
- [Calendar file and alarm verification](docs/evidence/local-calendar-export.md) and [seven-day core-read measurement procedure](docs/verification/seven-day-core-availability.md)

From `CarCareLog/`, run `py -3 -m unittest discover -s tests -v` on Windows or `python3 -m unittest discover -s tests -v` on macOS or Linux. The tests use temporary databases and a loopback stand-in for the model runtime. They check the application's handling of drafts, failures, and timeouts. Model accuracy and latency come from the evaluation tool, not from the unit tests.
