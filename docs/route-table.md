# Product entry point to use case audit

Revision: local vision build, November 22, 2026. Covers registered HTTP operations and user-triggered product entries, including text and photo receipt drafting with the pinned local model. UC IDs and names come from the native T18 model.

| Product entry | HTTP operation | Use case | Function | Handler | Status |
|---|---|---|---|---|---|
| Select vehicle | GET /api/vehicles | UC.1, UC.2, UC.3, UC.4 prerequisite | F.2.1 | app.py vehicle list | Implemented; selection only, not login |
| Create / edit vehicle | POST /api/vehicles; PUT /api/vehicles/{id} | UC.1 vehicle-data alternative | F.2.2.1 | app.py vehicle adapters | Implemented local adapter |
| Load classroom sample | POST /api/demo | None; development fixture | F.2.1 | seed_demo | Justified non-use-case entry; empty database only |
| Confirm a new record | POST /api/records | UC.1 Manage Maintenance Records, scenario B | F.2.2.1, F.2.2.3 | function_f22.py routing and transaction | Saves any additional performed services with one invoice total. A new UI save checks for same-vehicle receipt matches under the SQLite writer lock. HTTP 409 includes matching IDs for review. A retry of the same committed operation returns its original ID. |
| Add record; Confirm & save in bundled mode | POST /api/records?include=dashboard | UC.1 scenario A, including UC.2 reminder output | F.2.2.1; F.2.2.3; F.2.2.4 | Same transaction, then app.py reads committed C.3 state and prepares the dashboard | Opt-in experiment. Uses the ordinary refresh when the bundled dashboard is unavailable |
| Edit record; Confirm & save | PUT /api/records/{id} | UC.1 correction alternative | F.2.2.3 | app.py record edit adapter | Implemented; explicit confirmation |
| Delete record | DELETE /api/records/{id} | UC.1 deletion alternative | F.2.2.3 | app.py record deletion adapter | Implemented local adapter |
| Dashboard / history / expenses | GET /api/dashboard?vehicle_id={id} | UC.1; UC.2 Review Maintenance Reminders; UC.3 Review Maintenance Expenses | F.2.2.4; F.2.1 | dashboard and calculate_maintenance_summary_and_reminders | Implemented |
| Add / edit reminder rule | POST /api/reminders | UC.2 interval configuration | F.2.2.4 | app.py reminder rule adapter | Implemented; rule source required |
| Remove reminder rule | DELETE /api/reminders/{id} | UC.2 configuration alternative | F.2.2.4 | app.py reminder removal | Implemented |
| Export selected records | GET /api/export?vehicle_id={id} | UC.1 export alternative | F.2.2.4; F.2.1 | csv_export | Implemented selected-vehicle CSV |
| Ask a history question, then open a source record | GET /api/answer?vehicle_id={id}&question={question} | UC.4 Ask Questions About Vehicle Records | F.2.2.4, F.2.1 | history.py recorded-data lookup | Supports total, oil, tire_rotation and brake_spending. An optional year selects the brake-spending period. The answer distinguishes brake-only amounts from unpriced brake work on mixed invoices. |
| Add record; Draft from a receipt; Draft with local AI | POST /api/receipt-draft | UC.1 receipt-assisted path | F.2.2.2 | app.py receipt_draft; receipt_runtime.py; function_f22.py review_receipt_draft | Implemented locally for pasted text or one JPEG/PNG up to 4 MiB. Text values are checked against the receipt and photo-derived values require visual comparison; the owner reviews it and saves through Confirm & save. HTTP 503 with `not_configured` or `runtime_unavailable` leaves the form for manual entry |
| Open Add record (draft panel state) | GET /api/receipt-assist | UC.1 receipt-assisted path | F.2.2.2 | app.py | Implemented; reports whether drafting is configured and returns the synthetic sample receipt. Does not contact the runtime |
| General AI question | No public generative route | UC.4 generative alternative | F.2.2.2 | Pending | The dashboard retains the fixed record-grounded history lookups. |
| Internal routing contract | POST /internal/v1/validate-and-route | UC.1 internal processing | F.2.2.1 | validate_and_route_owner_request | Implemented localhost adapter, no standalone UI |
| Internal confirmed transaction | POST /internal/v1/confirmed-transaction | UC.1 internal processing | F.2.2.3 | coordinate_confirmed_record_transaction | Implemented localhost adapter |
| Internal prepared information | POST /internal/v1/prepare-information | UC.1; UC.2; UC.3 internal processing | F.2.2.4 | calculate_maintenance_summary_and_reminders | Implemented localhost adapter |
| Internal AI boundary | POST /internal/v1/coordinate-ai | UC.1 text or photo receipt; UC.4 general questions remain open | F.2.2.2 | Same handler as POST /api/receipt-draft | Implemented localhost adapter for `kind: receipt`; HTTP 503 without the runtime, no automatic write |
| Static application files | GET /; GET /app.js; GET /styles.css | All UI entry points above | F.2.1 | frontend/index.html, app.js, styles.css | Presentation assets, not separate use cases |

The default single-owner entry point exposes the internal adapters on loopback. The optional account entry point returns 404 for the internal adapters and authenticates the listed product routes, including history, export, receipt drafting and demo seeding. Owner confirmation is still required to save a record. Neither mode offers a vehicle-deletion operation.

### Additional routes in local account mode

| Method and route | Result |
| --- | --- |
| GET / or /signin | Sign-in or registration form when signed out. Dashboard when signed in. |
| POST /api/auth/register | Takes a demo username and password, creates an empty ledger and signs the owner in. |
| POST /api/auth/login | Validates credentials and issues a new session. |
| GET /api/auth/session | Returns the current username for a valid session. |
| POST /api/auth/logout | Revokes the current session. |
| GET /health | Returns a program status without account or ledger data. |

This entry point binds to 127.0.0.1. All mutations require the configured local origin. The browser identifies its current workspace so that a form opened before an account switch cannot save into the newly signed-in owner's ledger. See [ADR 013](adr-013-local-owner-accounts.md).
