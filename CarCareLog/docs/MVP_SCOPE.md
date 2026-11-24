# CarCareLog MVP scope

This prototype implements the core manual workflow in the team's stakeholder requirements document. It is a development starting point, not a claim that all 18 requirements or all course deliverables are complete.

| Requirement | Prototype coverage | Evidence / remaining work |
| --- | --- | --- |
| SR01 | Implemented | Add, edit or delete a single- or multi-service record for the selected vehicle. New receipt entries can be compared with earlier records before saving. |
| SR02 | Implemented for core workflow | Current mileage and descending service timeline; client-side service/provider search and date-range filters. |
| SR03–SR05 | Partial | The local vision model drafts from text or one JPEG/PNG. The app checks text provenance and flags all image-derived values for human comparison before Confirm & save. A timed usability study against the 180-second criterion remains open. |
| SR06 | Partial | Owner-confirmed intervals support pasted text, PDF and direct retrieval from selected publisher sites. Pages and fingerprints preserve source evidence. The owner checks edition, applicability and conditions. Complex tables can require manual entry. |
| SR07–SR08 | Implemented | Recompute on mileage changes and record add/edit/delete. Mileage/time due and upcoming states tested. |
| SR09 | Implemented | Exact-cent total and monthly spending use the receipt-level Maintenance/Repair category. A multi-service invoice contributes its total once. |
| SR10–SR11 | Partial | Four fixed lookups cite source records for total spending, last oil change, tire-rotation mileage and annual brake spending. A mixed invoice with no separate brake price leaves the exact brake total unknown. Typed questions support selected-vehicle record calculations and retrieval, or quotations from the active manual. Evidence gaps remain explicit. |
| SR12 | Implemented | CSV exports all confirmed records for the selected vehicle; Unicode and spreadsheet formula escaping tested. |
| SR13 | Partial, optional local account mode | With `--accounts`, each signed-in owner uses a separate SQLite ledger. [HTTP regression checks](../tests/test_owner_site.py) exercise blocked signed-out access, account switching and cross-account reads and writes. Default single-owner mode assumes a private computer. Independently administered or network-hosted service is outside this test scope. |
| SR14 | Pending | No seven-day availability measurement has been performed. |
| SR15 | Supported | Core record operations run independently of AI. A controlled timeout test verifies that the ledger remains unchanged and manual saving still works. |
| SR16 | Implemented for the local build | Repeatable checks cover CRUD, reminders, expenses, exports, fixed grounded lookup, receipt drafts and checks, and an end-to-end smoke test in CI on three operating systems. `tools/evaluate_receipts.py` evaluates the real model on 20 labeled receipts. |
| SR17 | Partial | The receipt adapter talks only to a loopback runtime and sends only the supplied text or image. Hosted AI and a production data-handling policy remain open. |
| SR18 | Implemented and exercised for local storage | Automatic hourly snapshots while running, startup integrity checks and local recovery. Two controlled drills recovered three records and $359.99 within one second, from fresh verified snapshots. See [drill results](../../docs/evidence/local-recovery-drill.json). Same-disk snapshots do not cover disk loss. |

## Demo flow

1. Start the app and load demo data into the empty database.
2. Explain that the three records and two intervals are examples.
3. Check the total and monthly cost breakdown.
4. Search for a provider or filter by service date.
5. Add an oil-change record from the sample receipt with **Draft with local AI**, review the flagged fields, then Confirm & save; the reminder recalculates. Manual entry works the same way without the model.
6. Edit a cost and check that the summary changes.
7. Ask the fixed oil-change question and show its source record ID.
8. Export CSV and restart the app to show data persistence.

## API overview

| Method | Path | Purpose |
| --- | --- | --- |
| GET / POST | `/api/vehicles` | List / create vehicles |
| PUT | `/api/vehicles/{id}` | Update vehicle name and odometer |
| GET | `/api/dashboard?vehicle_id={id}` | Records, reminders and cost summary |
| POST | `/api/records` | Confirm and save a record |
| POST | `/api/receipt-draft` | Draft a record from receipt text or image with the local model (nothing is saved) |
| GET | `/api/receipt-assist` | Whether AI drafting is on, plus the sample receipt |
| PUT / DELETE | `/api/records/{id}` | Edit / delete a record |
| POST | `/api/reminders` | Configure or replace a service interval |
| DELETE | `/api/reminders/{id}` | Remove an interval |
| GET | `/api/export?vehicle_id={id}` | Export full confirmed history |
| GET | `/api/answer?vehicle_id={id}&question=oil` | Last recorded oil change |
| GET | `/api/answer?vehicle_id={id}&question=total` | Total recorded cost |
| POST | `/api/demo` | Explicitly load sample data into an empty database |

JSON requests use `Content-Type: application/json`. Distances are whole kilometers, costs are USD with at most two decimal places, and service dates cannot be in the future. Unknown record IDs return 404; invalid data returns 400.
