# CarCareLog MVP scope

This prototype implements the core manual workflow in the team's stakeholder requirements document. It is a development starting point, not a claim that all 18 requirements or all course deliverables are complete.

| Requirement | Prototype coverage | Evidence / remaining work |
| --- | --- | --- |
| SR01 | Implemented | Add/edit/delete selected-vehicle records. API lifecycle test. |
| SR02 | Implemented for core workflow | Current mileage and descending service timeline; client-side service/provider search and date-range filters. |
| SR03–SR05 | Partial | The local vision model drafts from text or one JPEG/PNG. The app checks text provenance and flags all image-derived values for human comparison before Confirm & save. A timed usability study against the 180-second criterion remains open. |
| SR06 | Partial | User supplies the manual reference for each interval. The app does not verify or retrieve that reference. |
| SR07–SR08 | Implemented | Recompute on mileage changes and record add/edit/delete. Mileage/time due and upcoming states tested. |
| SR09 | Implemented | Exact-cent total and monthly costs split by Maintenance/Repair category. |
| SR10–SR11 | Partial | Two fixed history queries cite record IDs or state insufficient evidence. Natural-language AI and manual-grounded answers are pending. |
| SR12 | Implemented | CSV exports all confirmed records for the selected vehicle; Unicode and spreadsheet formula escaping tested. |
| SR13 | Pending | Local loopback server only. No accounts, owner authorization or multi-user access control. |
| SR14 | Pending | No seven-day availability measurement has been performed. |
| SR15 | Supported | Core record operations run independently of AI. A controlled timeout test verifies that the ledger remains unchanged and manual saving still works. |
| SR16 | Implemented for the local build | Repeatable checks cover CRUD, reminders, expenses, exports, fixed grounded lookup, receipt drafts and checks, and an end-to-end smoke test in CI on three operating systems. `tools/evaluate_receipts.py` evaluates the real model on 20 labeled receipts. |
| SR17 | Partial | The receipt adapter talks only to a loopback runtime and sends only the supplied text or image. Hosted AI and a production data-handling policy remain open. |
| SR18 | Pending | Stop-and-copy backup instructions exist; automated 24-hour recovery guarantees are not implemented. |

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
