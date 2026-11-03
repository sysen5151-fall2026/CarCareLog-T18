# Model requirement to implementation traceability

Revision: TA4 update, 3 November 2026. Code root: `CarCareLog/`. Native model snapshot: consolidated T18, 31 October 2026. Requirement numbers are document-scoped; native IDs disambiguate them.

All 22 populated ASR leaves are listed. A test name records selected evidence, not full requirement closure. The native requirements remain Draft. Exact statements are retained in `docs/requirements-baseline.json`.

| Requirement and native ID | Function / mechanism | Module | Named tests in CarCareLog/tests/test_functional_requirements.py | Evidence and outstanding scope |
|---|---|---|---|---|
| SRD 1.4.1.2 / 263241 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py and backend/app.py | test_SRD_1_4_1_2_manual_requested_operation | Manual end-to-end subset. AI and authenticated owners remain open. |
| ASR 1.1.1 / 279121 | F.2.2.3 / C.2.3 | CarCareLog/backend/function_f22.py | test_ASR_1_1_1_stored_confirmation_matches_persisted_id | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.1.2 / 279120 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | test_ASR_1_2_1_reject_unconfirmed_transaction | Local confirmation / selected-vehicle subset only; no authenticated owner isolation. |
| ASR 1.1.3 / 279119 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | None; planned | Planned; no passing acceptance evidence. External AI or owner isolation not implemented. |
| ASR 1.1.4 / 279118 | F.2.2.4 / C.2.4 | CarCareLog/backend/function_f22.py | test_ASR_1_1_4_rule_input_requires_source_and_real_interval | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.1.5 / 279117 | F.2.2.1 / C.2.1 | CarCareLog/backend/function_f22.py | test_ASR_1_4_1_route_existing_vehicle | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.1.6 / 279116 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | None; planned | Planned; no passing acceptance evidence. External AI or owner isolation not implemented. |
| ASR 1.1.7 / 279115 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | test_ASR_1_1_7_ai_unavailable_is_explicit_without_write | Unavailable / unimplemented signaling only; no successful external AI or operator incident pipeline. |
| ASR 1.1.8 / 279114 | F.2.2.1 / C.2.1 | CarCareLog/backend/function_f22.py | test_ASR_1_1_8_request_input_rejects_missing_vehicle | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.1.9 / 279113 | F.2.2.4 / C.2.4 | CarCareLog/backend/function_f22.py | test_ASR_1_1_9_selected_vehicle_record_input | Local confirmation / selected-vehicle subset only; no authenticated owner isolation. |
| ASR 1.2.1 / 279109 | F.2.2.3 / C.2.3 | CarCareLog/backend/function_f22.py | test_ASR_1_2_1_reject_unconfirmed_transaction | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.2.2 / 279112 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | None; planned | Planned; no passing acceptance evidence. External AI or owner isolation not implemented. |
| ASR 1.2.3 / 279111 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | None; planned | Planned; no passing acceptance evidence. External AI or owner isolation not implemented. |
| ASR 1.2.4 / 279110 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | test_ASR_1_1_7_ai_unavailable_is_explicit_without_write | Unavailable / unimplemented signaling only; no successful external AI or operator incident pipeline. |
| ASR 1.2.5 / 279108 | F.2.2.3 / C.2.3 | CarCareLog/backend/function_f22.py | test_ASR_1_3_1_internal_record_store_roundtrip | Local confirmation / selected-vehicle subset only; no authenticated owner isolation. |
| ASR 1.2.6 / 279107 | F.2.2.4 / C.2.4 | CarCareLog/backend/function_f22.py | test_ASR_1_2_6_prepared_information_output | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.3.1 / 279102 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | test_ASR_1_3_1_internal_record_store_roundtrip | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.3.2 / 279101 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | test_ASR_1_3_2_web_interface_output_matches_internal_summary | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.4.1 / 279106 | F.2.2.1 / C.2.1 | CarCareLog/backend/function_f22.py | test_ASR_1_4_1_route_existing_vehicle | Local confirmation / selected-vehicle subset only; no authenticated owner isolation. |
| ASR 1.4.2 / 279105 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | test_ASR_1_4_2_external_AI_boundary_explicitly_unimplemented | Unavailable / unimplemented signaling only; no successful external AI or operator incident pipeline. |
| ASR 1.4.3 / 279104 | F.2.2.3 / C.2.3 | CarCareLog/backend/function_f22.py | test_ASR_1_4_3_commit_then_return_record_id | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 1.4.4 / 279103 | F.2.2.4 / C.2.4 | CarCareLog/backend/function_f22.py | test_ASR_1_4_4_or_thresholds_and_confirmed_source; test_SR08_upcoming_distance_uses_500_miles_in_km; test_SR08_upcoming_time_uses_30_day_inclusive_window | Selected local manual-path cases. Full requirement acceptance remains open. |
| ASR 2.1.1 / 279128 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | None; planned | Planned; no passing acceptance evidence. External AI or owner isolation not implemented. |

## FCS and system-wide flow-down

| Source | Component contribution | Test evidence | Status |
|---|---|---|---|
| SRD 2.1.2 to FCS.2.1.2 / 289490 | Synthesis: manual CRUD does not depend on external AI | test_FCS_2_1_2_manual_path_independent_of_external_AI | Four local read/write cases; seven-day >=99% uptime unmeasured |
| SR08 / 245392; ASR 1.4.4 | Upcoming window 30 days OR 500 miles, with km storage | test_SR08_upcoming_distance_uses_500_miles_in_km; test_SR08_upcoming_time_uses_30_day_inclusive_window | Distance conversion and boundary cases checked; usability not established |

## ICOMs and deployment

Inputs: validated owner service request, selected-vehicle stored records and stored confirmation. Controls: confirmation policy, operation configuration and referenced interval rules. Outputs: confirmed service record, committed ID and prepared vehicle information. Mechanisms: C.2.1-C.2.4 responsibilities in one Python process; C.3 SQLite.

`contracts/api-v1.yaml` exposes four internal contract adapters with function IDs and decomposition tags. They invoke the existing functions; external AI returns HTTP 503 and stores no proposal. Internal DTOs are revalidated before persistence. No public deployment or owner authentication is claimed.

Native ASR/CRS/FCS allocations remain unchanged. The test docstrings quote their native requirement statements; scope notes limit the claim to the behavior actually exercised.
