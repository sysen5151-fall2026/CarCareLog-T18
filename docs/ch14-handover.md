# CarCareLog local pilot handover

This guide is for a maintainer receiving the T18 build. The local browser application supports vehicle histories, confirmed service records and maintenance reminders. The optional Ollama adapter can draft receipt fields from text or a JPEG/PNG. One person operates the classroom instance on one computer.

## Installation and first run

1. Check out the release revision recorded in the report. Install a Python version exercised by the repository CI (Python 3.12 is a suitable choice) and check `python --version`. The application uses SQLite and the Python standard library. No Python dependencies need downloading.
2. For local receipt inference, install Ollama from its official distribution. Start Ollama, run `ollama pull qwen3.5:4b`, and use `ollama list` to check the installed tag. Verify the runtime, model weights and projector against the release evidence before interpreting new accuracy results. The application contacts Ollama on loopback port 11434.
3. Use the [repository README](../README.md) commands to set `CARCARE_DB` to a new, disposable path and `CARCARE_OLLAMA_MODEL` to `qwen3.5:4b`. From the repository root, run `python CarCareLog/backend/app.py`. Open `http://127.0.0.1:8000`. Note the active database path printed at startup so it can be recovered later. Keep the service on loopback.
4. Load the synthetic demo data into the empty database. Select the demo vehicle and compare its baseline count and total with the walkthrough. Use **Add service record** to paste receipt text or choose one JPEG/PNG under 4 MiB. Review the proposal beside the source. Correct flagged fields, then choose **Confirm & save**. Check the new amount, record count and selected vehicle and reload to confirm persistence.
5. In a disposable database, run `python CarCareLog/tools/smoke_test.py` to reproduce the fixture-backed end-to-end check. Follow the root README for the real-model test. Run `python -m unittest discover -s tests -v` from the CarCareLog application directory. Reproduce Chapter 14 analysis from the repository root with `python docs/verification/chapter14_verify.py CarCareLog PATH_TO_NEW_RESULTS`; the results directory must be writable and loopback allowed.

## Data dependencies and limits

| Input | Origin and refresh | Consequence of an error or loss |
|---|---|---|
| Vehicle and confirmed records | Owner chooses vehicle and explicitly confirms an entry. SQLite at CARCARE_DB is the authoritative history. | An incorrect vehicle or cost changes records, expenses and reminders. Compare the selected dashboard with the receipt before confirming. |
| Odometer and maintenance intervals | Owner supplies readings and intervals from a referenced service manual. Update after a new reading or revised interval. | A stale reading or incorrect interval produces misleading reminder dates or distances. Review against the owner's manual. |
| Receipt text or photo | The owner supplies one source per draft. Changing that source invalidates values supplied by the previous draft. Request a new draft or complete the form manually. | Blur, cropped totals, ambiguous dates or wrong units can produce plausible values. Check each field and performed service against the receipt before saving. |
| Ollama service, weights and projector | Installed separately. Record the version and digests when an operator changes a dependency. | A missing runtime, wrong model or timeout prevents a draft. The manual path and existing records remain available in the pilot fixture. |

The build has no production account-authentication boundary, seven-day availability measurement, or completed first-time-owner usability study. Keep the pilot on loopback. For V03, follow the [field protocol](verification/receipt-owner-study.md) with ten first-time owners and record each observation with the [study tool](../CarCareLog/tools/receipt_owner_study.py). The [earlier synthetic-image results](evidence/chapter14-qwen35-receipt-images.md) cover six fields on the previous schema. Keep those results separate from owner timings and from any new multi-service evaluation.

When one receipt covers several services, confirm the performed services together and enter the invoice total once. Each matching service interval then references that record. The four history questions use confirmed records for the selected vehicle. Open the cited entries to verify an answer. For a mixed invoice without separate prices, the brake-spending answer identifies the unallocated work.

## Ownership, maintenance and likely incidents

The application maintainer owns Python, the HTTP contract and regression checks; the local operator owns the Ollama service and the approved database path. The vehicle owner checks source values and authorizes the write. At release or dependency change, rerun the functional acceptance suite, smoke check, field-accuracy benchmark and outage test. Check available disk space, preserve an authorized backup and verify a sample restore before treating history as recoverable.

| Symptom | First checks | Recovery and evidence |
|---|---|---|
| Draft fails or times out | Check the local Ollama process, tag, projector and port. Check whether the image type and size are supported. | Proceed using manual entry; capture the reason and elapsed time without logging receipt contents. Repeat one known synthetic receipt after repair. |
| Draft looks plausible but disagrees with the receipt | Compare date, unit, total, service item, category and provider with the source, especially a subtotal mistaken for the total. | Correct the preview or discard it. Confirm only after checking the vehicle. Preserve a synthetic reproducer with expected labels. |
| Duplicate warning appears when saving | Compare the candidate with the existing records shown for the same vehicle, date, shop and exact amount. | Open the previous entry if it is the same purchase. If there were two separate purchases, explicitly confirm a second save. |
| Expected history is missing or expense total is wrong | Check the selected vehicle and actual CARCARE_DB path. Compare persisted rows and total cents in a copy of the database. | Preserve the original, restore an authorized backup to a separate path and compare counts/totals. Do not overwrite the only recoverable copy. |

## Retirement

The owner decides whether records must be exported or retained under the applicable agreement. Before retiring the pilot, verify the export against a selected vehicle, stop both the application and its local model worker, and inventory the database, SQLite sidecars, backups, exported files, source receipts and temporary evidence. Remove each approved copy under the owner's retention instructions. Remove the Ollama model only after checking whether other applications need it. Review browser downloads, any saved/cached drafts, benchmark outputs and developer logs for receipt content. Record what was retained, its custodian, and what was removed. T18 specifies no automatic deletion or retention period and makes no secure-erasure guarantee.

The [T18 verification suite, entity 319943](https://cloud.innoslate.com/cornell/p/746/database/entity/319943) holds cases V01–V08. V01 is entity 319944. V02–V08 are entities 319968–319974, in order. Use the case relationships and each recorded disposition alongside the [protocol](verification/chapter14-protocol.md) and [results](verification/chapter14-results.json).

### Receipt review and history update

The updated local model produced 20 drafts for the 20 clean synthetic receipt photos. Across the six labeled fields, 119 of 120 matched and 19 of 20 receipts matched in full. One category error was flagged for review. The first draft took 30.324 seconds, with a 21.494-second warm median and 25.419-second warm p95. No request timed out. The labels grade the six main fields. Additional service suggestions and first-time owner performance require separate evidence. [Measured results](evidence/receipt-upgrade-image-benchmark.json).

The Chrome workflow regression exercises old-source invalidation, individual owner edits, one invoice updating two reminders, a duplicate save with a lost response, and cited records for brake spending and tire rotation. It uses a deterministic receipt model, the product's own HTTP handlers and an isolated SQLite ledger. Run instructions are in the [browser regression](../CarCareLog/tests/receipt_workflow.browser.cjs). For the private photo and owner trials, use the [study procedure](verification/receipt-owner-study.md).

The T18 native model records the implementation in [UC.1](https://cloud.innoslate.com/cornell/p/746/database/entity/199123), [UC.4](https://cloud.innoslate.com/cornell/p/746/database/entity/199126), [F.2.2.2](https://cloud.innoslate.com/cornell/p/746/database/entity/279063), and [F.2.3](https://cloud.innoslate.com/cornell/p/746/database/entity/245228). [V03](https://cloud.innoslate.com/cornell/p/746/database/entity/319969) retains its ten-owner acceptance criterion. Real camera-photo accuracy and representative-owner completion times remain unmeasured.
