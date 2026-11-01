# F.2.2 implementation traceability

Product root is `CarCareLog/`. Model snapshot: T18 consolidation, 31 October 2026.
Branch: `codex/milestone2-video`. A local test result is not a GitHub CI run.

Parent system functional requirement: SRD **1.4.1.2 Coordinate Vehicle Maintenance Information**, entity 263241, allocated to F.2.2 / C.2.
The component specification contains CRS.1–CRS.4 and ASR functional, input/output and interface requirements. The 13 retained FCS requirements add useful component interface, processing and quality flow-down constraints; they do not replace the system SRD.

| Function ID | Mechanism | Module and callable | Requirement / component source | Test name in CarCareLog/tests/test_functional_requirements.py | Scope |
|---|---|---|---|---|---|
| F.2.2.1 | C.2.1 | CarCareLog/backend/function_f22.py: validate_and_route_owner_request | CRS.1; ASR 1.4.1; FCS 1.4.1 | test_ASR_1_4_1_route_existing_vehicle | Selected-vehicle and operation checks. Owner authentication remains planned. |
| F.2.2.2 | C.2.2 | CarCareLog/backend/function_f22.py: coordinate_ai_requests_and_responses | CRS.2; ASR 1.4.2; FCS 1.4.2 | test_ASR_1_4_2_external_AI_boundary_explicitly_unimplemented | Reserved boundary raises NotImplementedError. No extraction or generative AI acceptance claim. |
| F.2.2.3 | C.2.3 | CarCareLog/backend/function_f22.py: coordinate_confirmed_record_transaction | CRS.3; ASR 1.2.1 and 1.4.3; FCS 1.4.3 | test_ASR_1_2_1_reject_unconfirmed_transaction; test_ASR_1_4_3_commit_then_return_record_id | Exact boolean confirmation, validated fields, committed ID. A client flag does not authenticate identity. |
| F.2.2.4 | C.2.4 | CarCareLog/backend/function_f22.py: calculate_maintenance_summary_and_reminders | CRS.4; ASR 1.4.4; FCS 1.4.4 | test_ASR_1_4_4_or_thresholds_and_confirmed_source | Confirmed-history cost and due-date/mileage calculations. |
| F.2.2 manual fallback | C.2 | CarCareLog/backend/app.py and function_f22.py | System SRD 2.1.2 to FCS 2.1.2 | test_FCS_2_1_2_manual_path_independent_of_external_AI | Synthesis contribution: manual path does not call external AI. Availability uptime remains unverified. |

## ICOM correspondence

- Inputs: validated owner service request, stored confirmation, authorized record query result. External AI response inputs remain modeled, unimplemented.
- Controls: explicit confirmation policy, local-demo configuration and referenced maintenance intervals.
- Outputs: confirmed service record, stored record identifier and prepared vehicle information.
- Mechanisms: C.2.1–C.2.4 responsibilities within one Python process and C.3 SQLite.

See `contracts/api-v1.yaml` for actual HTTP operations and in-process/SQLite flow extensions. Internal model arrows are not all HTTP calls.

## Verification limits

The 10 regression cases plus 6 requirement-linked cases check selected manual-path behavior. They do not establish authenticated multi-owner isolation, receipt OCR, external AI performance, seven-day availability or full requirement closure. The recorded-data answer endpoint is deterministic.
The existing prototype uses 30 days / 1,000 km for Upcoming status. The SRD's 500-mile criterion requires an explicit model/product reconciliation before acceptance.
Native Innoslate requirement links remain the source of requirements allocation. Code mappings in this table are implementation evidence, not new model relationships.
