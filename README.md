# CarCareLog

Cornell SYSEN 5151 · Team 18 · November 18, 2026 product progress check

CarCareLog keeps a vehicle's confirmed service history, costs, and maintenance reminders together. The classroom demo follows **UC.1 Manage Maintenance Records** from manual entry to a saved oil change, then reloads the history to verify the write.

## Run the classroom demo

Use Python 3.10 or later and a browser. The manual path uses Python's standard library and SQLite.

From the repository root, open PowerShell and run:

```powershell
$env:CARCARE_DB = Join-Path ([System.IO.Path]::GetTempPath()) ("CarCareLog-demo-" + [guid]::NewGuid() + ".db")
$env:CARCARE_PORT = '8000'
Remove-Item Env:CARCARE_OLLAMA_MODEL -ErrorAction SilentlyContinue
py -3 CarCareLog/backend/app.py
```

On macOS or Linux, use:

```bash
CARCARE_DB="$(mktemp)" CARCARE_OLLAMA_MODEL= python3 CarCareLog/backend/app.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), select **Load demo data**, and choose the demo vehicle. Open **Add record**, enter an oil change with today's date and the vehicle's current odometer reading, and enter **89.99 USD**. Select **Confirm & save** once. Check that the timeline gains one row and the total increases by 89.99 USD, then refresh the page and show the saved row again. Use a fresh demo database for each rehearsal or round. Stop the server with Ctrl+C.

For a persistent local workspace, omit the temporary database override. Keep real vehicle records and secrets off the shared screen. If port 8000 is in use, set `CARCARE_PORT` to a free port and open that port in the browser.

## OpsCon and as-built system

Open [T18 Universe Context](https://cloud.innoslate.com/cornell/p/746/diagrams/asset/184237). The chart marks the four asset nodes by implementation status.

| OpsCon asset | Status | Location in this build |
| --- | --- | --- |
| Ext.1 Vehicle Owner | Working | [Web interface](CarCareLog/frontend/index.html) and [browser interactions](CarCareLog/frontend/app.js) support the manual owner workflow. |
| C.0 CarCareLog System | Partial | C.1 is the browser UI. C.2 uses the [HTTP service](CarCareLog/backend/app.py) and [F.2.2 coordination](CarCareLog/backend/function_f22.py). C.3 uses SQLite through the backend. The core manual path works. Owner authentication and full AI integration remain open. |
| Ext.2 AI Model Runtime | Partial | The [receipt-text adapter](CarCareLog/backend/receipt_runtime.py) can call a configured local Ollama runtime. A local test double verifies draft handling and the timeout fallback. Browser receipt entry, a pinned real model, real-model validation, and hosted integration remain open. |
| Ext.3 Application Operator | Not yet built | The operator can start and stop the prototype manually. A dedicated operator interface and automated recovery are pending. |

The service provider supplies receipts to the owner outside the application. There is no direct service-provider integration.

## Use-case coverage

| Use case | Current build |
| --- | --- |
| UC.1 Maintenance records | Manual create, edit, delete, search, CSV export, and explicit confirmation. The optional backend receipt-text path returns a draft for review. |
| UC.2 Maintenance reminders | A rule uses a source reference and a mileage or calendar interval. The separate warning window is 500 international miles (804.672 km) or 30 days from a due limit. |
| UC.3 Maintenance expenses | The dashboard shows recorded total and monthly costs based on confirmed service records. |
| UC.4 Record questions | Two predefined lookups return the last oil change or total cost with source record IDs. General questions and answers grounded in a vehicle manual remain open. |

## Chapters 11 and 12

[ADR 011](docs/adr-011-receipt-runtime.md) records the choice of SA.A, the local Ollama adapter, for the opt-in receipt-text pilot. SA.B uses GPT-6.1 Sol in the hosted cost comparison. The prototype does not use that hosted service. The [risk register](docs/risks.md) links to the native Innoslate matrix. The R2 timeout test confirms an unavailable response, an unchanged ledger, and a successful manual save. A separate fixture checks that even a well-formed but erroneous draft requires owner confirmation.

Next steps are to pin and validate a real local model using labeled sample receipts, integrate the draft review screen, and reproduce the build on a clean machine. Owner sign-in, data isolation, and operator recovery remain separate implementation tasks.

## Tests and related files

- [Interface contract](contracts/api-v1.yaml), [route table](docs/route-table.md), and [traceability](docs/traceability.md)
- [Receipt and timeout tests](CarCareLog/tests/test_receipt_runtime.py) and [requirement coverage](CarCareLog/docs/MVP_SCOPE.md)
- [Chapter 10 simulation evidence](docs/modeling-and-simulation.md) and [historical Milestone 2 demo](docs/DEMO_RELEASE.md)

Run `py -3 -m unittest discover -s tests -v` from `CarCareLog/` on Windows. Use `python3` instead of `py -3` on macOS or Linux. The tests use temporary databases and loopback HTTP. They do not measure real-model accuracy, inference latency, or production availability.
