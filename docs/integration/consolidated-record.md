# Consolidated implementation and integration record

Release product source: eb70a82. Historical local-text baseline: c28fae0, with the score audit on e531e51. Use the Git revision and repository file paths to reproduce. The Chapter 14 raw file hashes are for the Windows checkout; LF/CRLF conversion changes a byte digest without changing the code.

## Complete need–requirement–function–module–test crosswalk

The 22 ASR rows use the versioned requirement register, function allocations, tests and scoped outcomes. The need column is an engineering crosswalk to the use each module serves. It is not a claim of a direct native edge for every pair. Native numbers and IDs in the requirement and function columns are retained. Supporting traces include UI, persistence, tools and fixtures. An open requirement remains open.

| Need | Requirement / native ID | Function / mechanism | Module | Test | Evidence / outstanding scope |
| --- | --- | --- | --- | --- | --- |
| EN01 · service history | ASR 1.1.1 / 279121 | F.2.2.3 / C.2.3 | CarCareLog/backend/function_f22.py | test_ASR_1_1_1_stored_confirmation_matches_persisted_id | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN02 · owner control | ASR 1.1.2 / 279120 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | test_ASR_1_2_1_reject_unconfirmed_transaction | Local confirmation / selected-vehicle subset only; no authenticated owner isolation. |
| EN10 · AI contract compliance | ASR 1.1.3 / 279119 | F.2.2.2 / C.2.2 | CarCareLog/backend/receipt_runtime.py and backend/app.py | test_ASR_1_1_3_operator_settings_set_model_port_and_timeout (test_receipt_runtime.py) | Operator settings by environment variable: model, loopback port, timeout. No operator interface. |
| EN03 · maintenance planning | ASR 1.1.4 / 279118 | F.2.2.4 / C.2.4 | CarCareLog/backend/function_f22.py | test_ASR_1_1_4_rule_input_requires_source_and_real_interval | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN08 · continuity | ASR 1.1.5 / 279117 | F.2.2.1 / C.2.1 | CarCareLog/backend/function_f22.py | test_ASR_1_4_1_route_existing_vehicle | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN02 · receipt creation | ASR 1.1.6 / 279116 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py and backend/receipt_runtime.py | test_ASR_1_1_6_browser_draft_converts_miles_and_saves_only_after_confirmation (test_receipt_runtime.py); test_receipt_review.py | Accepts date, mileage, item, category, cost, and provider from the local runtime, checks them, and returns them for review. The labeled text and image evaluations are in tools/evaluate_receipts.py and tools/evaluate_receipt_images.py. |
| EN05 / EN08 · evidence and continuity | ASR 1.1.7 / 279115 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | test_ASR_1_1_7_ai_unavailable_is_explicit_without_write; test_R2_runtime_timeout_preserves_ledger_and_manual_save; test_malformed_runtime_reply_is_an_explicit_failure (test_receipt_runtime.py) | AI failure responses for receipt drafts. Evidence-backed answers to general questions remain open. |
| EN01 · service history | ASR 1.1.8 / 279114 | F.2.2.1 / C.2.1 | CarCareLog/backend/function_f22.py | test_ASR_1_1_8_request_input_rejects_missing_vehicle | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN07 · data control | ASR 1.1.9 / 279113 | F.2.2.4 / C.2.4 | CarCareLog/backend/function_f22.py | test_ASR_1_1_9_selected_vehicle_record_input | Local confirmation / selected-vehicle subset only; no authenticated owner isolation. |
| EN01 / EN02 · confirmed history | ASR 1.2.1 / 279109 | F.2.2.3 / C.2.3 | CarCareLog/backend/function_f22.py | test_ASR_1_2_1_reject_unconfirmed_transaction | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN02 · receipt creation | ASR 1.2.2 / 279112 | F.2.2.2 / C.2.2 | CarCareLog/backend/receipt_runtime.py | test_ASR_1_2_2_receipt_request_sends_text_only_with_pinned_settings; test_photo_draft_sends_pixels_only_and_requires_visual_review_and_confirmation (test_receipt_runtime.py) | Local extraction sends only the supplied text or one JPEG/PNG image with the pinned model settings and JSON schema. |
| EN05 · evidence-based answers | ASR 1.2.3 / 279111 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | None; planned | Planned; no passing acceptance evidence. External AI or owner isolation not implemented. |
| EN08 · continuity | ASR 1.2.4 / 279110 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | test_ASR_1_1_7_ai_unavailable_is_explicit_without_write | Unavailable / unimplemented signaling only; no successful external AI or operator incident pipeline. |
| EN07 · data control | ASR 1.2.5 / 279108 | F.2.2.3 / C.2.3 | CarCareLog/backend/function_f22.py | test_ASR_1_3_1_internal_record_store_roundtrip | Local confirmation / selected-vehicle subset only; no authenticated owner isolation. |
| EN03 / EN04 · planning and expense | ASR 1.2.6 / 279107 | F.2.2.4 / C.2.4 | CarCareLog/backend/function_f22.py | test_ASR_1_2_6_prepared_information_output | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN01 · record persistence | ASR 1.3.1 / 279102 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | test_ASR_1_3_1_internal_record_store_roundtrip | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN01 / EN02 · selected-vehicle operation | ASR 1.3.2 / 279101 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | test_ASR_1_3_2_web_interface_output_matches_internal_summary | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN01 · service history | ASR 1.4.1 / 279106 | F.2.2.1 / C.2.1 | CarCareLog/backend/function_f22.py | test_ASR_1_4_1_route_existing_vehicle | Local confirmation / selected-vehicle subset only; no authenticated owner isolation. |
| EN02 / EN05 · draft and answer | ASR 1.4.2 / 279105 | F.2.2.2 / C.2.2 | CarCareLog/backend/function_f22.py | test_ASR_1_4_2_external_AI_boundary_explicitly_unimplemented; test_receipt_draft_and_unavailable_responses_match_the_contract (test_receipt_runtime.py) | Receipt drafts are coordinated end to end; question generation still returns the explicit unavailable result. |
| EN01 / EN02 · confirmed history | ASR 1.4.3 / 279104 | F.2.2.3 / C.2.3 | CarCareLog/backend/function_f22.py | test_ASR_1_4_3_commit_then_return_record_id | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN03 / EN04 · planning and expense | ASR 1.4.4 / 279103 | F.2.2.4 / C.2.4 | CarCareLog/backend/function_f22.py | test_ASR_1_4_4_or_thresholds_and_confirmed_source; test_SR08_upcoming_distance_uses_500_miles_in_km; test_SR08_upcoming_time_uses_30_day_inclusive_window | Selected local manual-path cases. Full requirement acceptance remains open. |
| EN07 · owner data control | ASR 2.1.1 / 279128 | F.2.2 / C.2 | CarCareLog/backend/function_f22.py | None; planned | Planned; no passing acceptance evidence. External AI or owner isolation not implemented. |
| EN01 / EN02 | SR01 245385; SR04 245388 | F.2.1 / C.1 | frontend/index.html; app.js; styles.css | test_page_learns_whether_ai_drafting_is_on; browser image fixture | Shows selected vehicle, draft fields, source preview, six checks and explicit confirmation. |
| EN02 / EN10 | SR03 245387; SR17 245404 | F.2.2.2 / C.2.2 → Ext.2 | backend/receipt_runtime.py | test_photo_draft_sends_pixels_only_and_requires_visual_review_and_confirmation | Schema-bound loopback text or image request, timeout and failure. |
| EN03 / EN04 | SR07 245391; SR09 245393 | F.2.2.4 / C.2.4 | backend/function_f22.py; backend/app.py | test_ASR_1_4_4_or_thresholds_and_confirmed_source | Confirmed rows drive reminders and integer-cent totals. |
| EN06 / EN07 | SR12 245396; SR13 245397 | F.2.1, F.2.2.4 | backend/app.py; frontend/app.js | test_vehicle_selection_limits_dashboard_and_export; test_csv_unicode_and_formula_escaping | Local selected-vehicle CSV and record filtering; multi-user authorization remains open. |
| EN05 | SR10 245394; SR11 245395 | F.2.2.2 / F.2.2.4 | backend/app.py; backend/function_f22.py | test_grounded_answers_and_insufficient_evidence | Deterministic total/last-oil lookup only. General evidence-backed model answers are unimplemented. |
| EN08 / EN11 | SR15 245400; SR18 245406 | F.2.2.3 / C.3 | backend/app.py; SQLite database | test_record_lifecycle_and_exact_costs; test_R2_runtime_timeout_preserves_ledger_and_manual_save | Local restart/read-back verified. Disaster recovery and seven-day operation remain open. |
| EN09 | SR16 245402 | F.4; release acceptance | tests/; tools/smoke_test.py; tools/measure_product.py; tools/evaluate_receipts.py; tools/compare_receipt_runtimes.py; tools/evaluate_receipt_images.py; docs/verification/chapter14_verify.py | CI functional suite; raw dated run files | Verification enablers; labeled synthetic data and seeded DB are fixtures. Backend __init__.py only marks the package. API contract, UI styles and sample receipt are linked to the exercised route. |

## Chapter-ordered provenance

The repository contains the following surviving artifacts. Current filenames, Git historical filenames and the group Drive index did not yield a contemporaneous generation log. No specific generation can be identified as reviewed, rejected or promoted from those artifacts. Reviewer identities and counts of promoted assumptions or rejected generations remain unknown; no entries have been reconstructed from memory.

| Chapter | Task | Surviving design record | Provenance limit |
| --- | --- | --- | --- |
| 1 | System context | Context boundary defines owner, local app and model runtime. | Course model; no contemporaneous generation record located. |
| 2 | Mission behavior | UC.1 makes the owner responsible for confirmation. | Use-case model; original generation/reviewer unavailable. |
| 3 | Stakeholder needs | EN01, EN02, EN08 and their stakeholder requirements anchor the pilot. | Need and requirement entities; original generation/reviewer unavailable. |
| 4 | Top-level functions | F.2 coordinates services. Automated functional checks cover selected flows. | Repository functional acceptance tests; original generation/reviewer unavailable. |
| 5 | Functional requirements | SRD/ASR baselines disambiguate scoped numbers by native ID. | docs/requirements-baseline.json; original generation/reviewer unavailable. |
| 6 | Use-case traces | UC.1 records, UC.2 reminders, UC.3 expenses, UC.4 limited lookup. | docs/route-table.md; original generation/reviewer unavailable. |
| 7 | First-level functions | IC-01 to IC-04 define exchanges; route and transaction contracts are explicit. | contracts/api-v1.yaml; original generation/reviewer unavailable. |
| 8 | Physical architecture | C.1 browser, C.2 service, C.3 store and Ext.2 runtime set deployment boundaries. | Native asset model and repository architecture; original generation/reviewer unavailable. |
| 9 | Second-level architecture | F.2.2.1–F.2.2.4 allocate validation, AI, persistence and summaries. | cf76c08; d9d8022; original generation/reviewer unavailable. |
| 10 | Executable simulation | UC.1 separate/bundled refresh compared against the operating product. | 55a5367; docs/modeling-and-simulation.md; original generation/reviewer unavailable. |
| 11 | System analysis | ADR 011 records the architecture choice and initial text-only evidence. | bf5755a; c28fae0; 4f51b64; original generation/reviewer unavailable. |
| 12 | Risk assessment | R1–R5 linked to controls; named failure tests exercise draft-only behavior and outage. | 919291a; docs/risks.md; original generation/reviewer unavailable. |

## Integration sequence and interface verification

The four-step risk-first sequence exercises Ext.2 (IC-03), draft review and routing, confirmed transactions, then the browser owner workflow. The native sequence diagram and original functional I² views remain in project 746.

| Interface | Contract and errors | Responsibility, load, and recorded result |
| --- | --- | --- |
| IC-01 · C.1 ↔ C.2 | JSON over same-origin HTTP; selected vehicle; km and USD on entry. Unsupported input, missing vehicle or unconfirmed save yields an explicit error. | Browser presents draft, service validates. Confirmed writes use a per-operation identifier. A2 exercised 30 sequences; Chrome fixture showed three→four rows only after confirmation. |
| IC-02 · C.2 ↔ C.3 | SQLite transaction; persisted record ID, vehicle and integer cents. Failed/duplicate operations must not add a second row. | C.2 validates before writing; C.3 commits; service reads the selected ledger back. 30/30 correct totals, zero unrelated rows. Repeated operation and restart covered by smoke/tests. |
| IC-03 · C.2.2 ↔ Ext.2 | One receipt text OR JPEG/PNG up to 4 MiB, loopback JSON request, structured draft or 503. Reject mixed, unsupported and oversized inputs before inference. | C.2.2 checks fields and owns timeout/failure reporting. Every image field requires visual review. Actual image run: 20/20 within configured 60 s, warm p95 28.458 s. |
| IC-04 · operator ↔ C.2 | Operator supplies local model/tag, port and timeout. Configuration/state exposed locally; unset or unavailable → explicit manual path. | Operator restores Ollama/tag; service owns error/status. Settings test confirms controls. Operator console, fleet monitoring and sustained-load qualification remain open. |

## Corrective actions

| Classification | Observed issue | Disposition |
| --- | --- | --- |
| D1 · code | Backend reminder threshold was 1,000 km. SR08 specifies 500 international miles (804.672 km) or 30 days. | d9d8022 corrects units; c66999a synchronizes the UI. Reuse the same boundary values in Ch5/9 specifications and CI. |
| D2 · interface specification | The route register previously described receipt images as unsupported while the new endpoint accepted them. This could lead a receiving team to implement the obsolete contract. | Separate the historical ADR 011 text path from ADR 012 and current route/contract; validate the accepted media, size, empty/mixed input and draft state at IC-03. Implicates Ch7–9. |
| D3 · verification code | The legacy derived v5 stored with the 11/22 raw timing was inconsistent with ADR 011’s continuous 2–60 s scale. | Retain raw timings and reproduce 0.899466 from 7.831 s via the score audit. Add an explicit scoring oracle for the limits and interpolation. Implicates Ch11. |

## Realization decisions and original model entities

| Topic | Decision | Native trace / remaining gap |
| --- | --- | --- |
| Receipt input and runtime | ADR 011 preserves Qwen2.5 3B text benchmark; ADR 012 records qwen3.5:4b and one text/photo source. | C.2.2 279069, Ext.2 199110, CO.2 199114, IC-03 loopback 319889. Historic alternatives remain historical. |
| Source evidence and persistence | A photo stays transient. Return proposed fields for visual review, then submit via ordinary explicit confirmation. | F.2.2.2 279063; 1.1.6 Accept Uploaded receipt and vehicle ID 263254; FCS.1.4.3 289487. Retention of a receipt archive is outside delivered scope. |
| Shared deployment and questions | The demo selects a vehicle locally. The only implemented questions are deterministic total/last-oil lookups. | SR13 245397 / ASR 2.1.1 279128 and ASR 1.2.3 279111 remain partial/open. Do not infer authentication or a general-purpose generative answer path. |

## External supply inventory

| Element | Selection and version | Terms and acceptance |
| --- | --- | --- |
| Make · T18 app and contract | Versioned Python service, JS/HTML/CSS, OpenAPI, SQLite schema and synthetic fixtures at the release revision. | No vendor API charge. Local receipt processing and isolated DB. Accept through unit, smoke, browser and image trials. |
| Reuse · Python and SQLite | PSF Python 3.12.14 + SQLite 3.53.1 in the Chapter 14 test environment. Standard library; no application pip requirements. | PSF licensing; SQLite core is public domain. Check interpreter/library versions; confirm a save/reload with exact cents. |
| Reuse · Ollama | Ollama 0.40.16 ran the actual vision benchmark on loopback. No hosted service key is required. | MIT-licensed runtime. Existing hardware, energy, download and maintenance time still cost resources. Check local endpoint, timeout and failure behavior. |
| Reuse · Qwen3.5 4B | Ollama qwen3.5:4b, GGUF Q4_K_M; blob a9d0a3e1d8c9…, vision projector e56a899b1540…. See ADR 012 for full pin. | Apache 2.0 model release. Fetch weights once and verify installed pins. Use synthetic PNGs to test six fields, latency and mandatory visual review. |

Primary supply references: [Qwen3.5 4B](https://ollama.com/library/qwen3.5:4b), [Ollama license](https://github.com/ollama/ollama/blob/main/LICENSE), [Python licensing](https://docs.python.org/3/license.html), [SQLite status](https://www.sqlite.org/copyright.html).

Consult the root README, the two dated benchmark records, ADR 011 (historical), [ADR 012](../adr-012-local-receipt-vision.md), [current handover](../ch14-handover.md), and [predeclared verification protocol](../verification/chapter14-protocol.md). For each new significant generation record date, tool, prompt reference, model entities, human reviewer and actual disposition at the time of review.

## Integration sequence in the team model

The four-step integration Action Diagram is T18 entity 319958. See the [native Innoslate diagram](https://cloud.innoslate.com/cornell/p/746/diagrams/action/319958) and the [unmodified Innoslate PNG export](native-integration-action-319958.png).
