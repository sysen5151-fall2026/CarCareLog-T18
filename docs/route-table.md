# Product entry point to use case audit

Revision: 3 November 2026. Covers every registered HTTP operation and user-triggered product entry, including internal adapters and justified development entries. UC IDs and names come from the native T18 model. Alternatives describe prototype paths, not new model entities.

| Product entry | HTTP operation | Use case | Function | Handler | Status |
|---|---|---|---|---|---|
| Select vehicle | GET /api/vehicles | UC.1, UC.2, UC.3, UC.4 prerequisite | F.2.1 | app.py vehicle list | Implemented; selection only, not login |
| Create / edit vehicle | POST /api/vehicles; PUT /api/vehicles/{id} | UC.1 vehicle-data alternative | F.2.2.1 | app.py vehicle adapters | Implemented local adapter |
| Load classroom sample | POST /api/demo | None; development fixture | F.2.1 | seed_demo | Justified non-use-case entry; empty database only |
| Add record; Confirm & save | POST /api/records | UC.1 Manage Maintenance Records, scenario B | F.2.2.1; F.2.2.3 | function_f22.py routing and transaction | Default manual path, followed by separate vehicle and dashboard reads |
| Add record; Confirm & save in bundled mode | POST /api/records?include=dashboard | UC.1 scenario A, including UC.2 reminder output | F.2.2.1; F.2.2.3; F.2.2.4 | Same transaction, then app.py reads committed C.3 state and prepares the dashboard | Opt-in experiment. Uses the ordinary refresh when the bundled dashboard is unavailable |
| Edit record; Confirm & save | PUT /api/records/{id} | UC.1 correction alternative | F.2.2.3 | app.py record edit adapter | Implemented; explicit confirmation |
| Delete record | DELETE /api/records/{id} | UC.1 deletion alternative | F.2.2.3 | app.py record deletion adapter | Implemented local adapter |
| Dashboard / history / expenses | GET /api/dashboard?vehicle_id={id} | UC.1; UC.2 Review Maintenance Reminders; UC.3 Review Maintenance Expenses | F.2.2.4; F.2.1 | dashboard and calculate_maintenance_summary_and_reminders | Implemented |
| Add / edit reminder rule | POST /api/reminders | UC.2 interval configuration | F.2.2.4 | app.py reminder rule adapter | Implemented; rule source required |
| Remove reminder rule | DELETE /api/reminders/{id} | UC.2 configuration alternative | F.2.2.4 | app.py reminder removal | Implemented |
| Export selected records | GET /api/export?vehicle_id={id} | UC.1 export alternative | F.2.2.4; F.2.1 | csv_export | Implemented selected-vehicle CSV |
| Ask total / last oil question | GET /api/answer?vehicle_id={id}&question=total or oil | UC.4 Ask Questions About Vehicle Records | F.2.2.4; F.2.1 | app.py recorded-data lookup | Implemented deterministic subset; no generative AI |
| Receipt upload / generative question | No successful external-AI route | UC.1 receipt-assisted path; UC.4 generative alternative | F.2.2.2 | coordinate_ai_requests_and_responses | Planned; contract adapter returns unavailable |
| Internal routing contract | POST /internal/v1/validate-and-route | UC.1 internal processing | F.2.2.1 | validate_and_route_owner_request | Implemented localhost adapter, no standalone UI |
| Internal confirmed transaction | POST /internal/v1/confirmed-transaction | UC.1 internal processing | F.2.2.3 | coordinate_confirmed_record_transaction | Implemented localhost adapter |
| Internal prepared information | POST /internal/v1/prepare-information | UC.1; UC.2; UC.3 internal processing | F.2.2.4 | calculate_maintenance_summary_and_reminders | Implemented localhost adapter |
| Internal external-AI boundary | POST /internal/v1/coordinate-ai | UC.1 / UC.4 planned AI processing | F.2.2.2 | coordinate_ai_requests_and_responses | 503 unavailable only; no successful extraction |
| Static application files | GET /; GET /app.js; GET /styles.css | All UI entry points above | F.2.1 | frontend/index.html, app.js, styles.css | Presentation assets, not separate use cases |

The application has no vehicle-delete or health endpoint. Unknown paths return 404. Local owner-confirmation flags are workflow controls, not authentication. All internal endpoints use the same localhost Host/Origin guard as product endpoints.
