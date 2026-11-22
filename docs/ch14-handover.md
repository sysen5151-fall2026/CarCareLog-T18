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
| Receipt text or photo | User supplies one source per draft. The application sends it to local Ollama. New photos trigger a fresh draft. | Blur, cropped totals, ambiguous dates or wrong units can produce plausible values. Image fields need manual visual review. Enter the record manually when the source is unclear. |
| Ollama service, weights and projector | Installed separately. Record the version and digests when an operator changes a dependency. | A missing runtime, wrong model or timeout prevents a draft. The manual path and existing records remain available in the pilot fixture. |

The build has no production account-authentication boundary, seven-day availability measurement, or completed first-time-owner usability study. Do not expose this pilot on a shared network. General vehicle question answering remains an explicit unavailable path.

## Ownership, maintenance and likely incidents

The application maintainer owns Python, the HTTP contract and regression checks; the local operator owns the Ollama service and the approved database path. The vehicle owner checks source values and authorizes the write. At release or dependency change, rerun the functional acceptance suite, smoke check, field-accuracy benchmark and outage test. Check available disk space, preserve an authorized backup and verify a sample restore before treating history as recoverable.

| Symptom | First checks | Recovery and evidence |
|---|---|---|
| Draft fails or times out | Check the local Ollama process, tag, projector and port. Check whether the image type and size are supported. | Proceed using manual entry; capture the reason and elapsed time without logging receipt contents. Repeat one known synthetic receipt after repair. |
| Draft looks plausible but disagrees with the receipt | Compare date, unit, total, service item, category and provider with the source, especially a subtotal mistaken for the total. | Correct the preview or discard it. Confirm only after checking the vehicle. Preserve a synthetic reproducer with expected labels. |
| Expected history is missing or expense total is wrong | Check the selected vehicle and actual CARCARE_DB path. Compare persisted rows and total cents in a copy of the database. | Preserve the original, restore an authorized backup to a separate path and compare counts/totals. Do not overwrite the only recoverable copy. |

## Retirement

The owner decides whether records must be exported or retained under the applicable agreement. Before retiring the pilot, verify the export against a selected vehicle, stop both the application and its local model worker, and inventory the database, SQLite sidecars, backups, exported files, source receipts and temporary evidence. Remove each approved copy under the owner's retention instructions. Remove the Ollama model only after checking whether other applications need it. Review browser downloads, any saved/cached drafts, benchmark outputs and developer logs for receipt content. Record what was retained, its custodian, and what was removed. T18 specifies no automatic deletion or retention period and makes no secure-erasure guarantee.
