# PMC2 UC 1 and UC 2 release

Release identifier: `PMC2-UC2-20261103`. Read the delivered `RELEASE_MANIFEST.json` for the exact commit and test/CI evidence. The manifest is packaged outside the repository to avoid embedding a commit's own hash inside its contents. This release keeps the same product behavior and native model relationships; it updates documentation and adds three UC.2 integration tests.

## Architecture

| Model responsibility | Physical asset | Implementation |
|---|---|---|
| F.2.1 Present CarCareLog Services | C.1 Web Interface | `CarCareLog/frontend/` forms and panels |
| F.2.2 Coordinate Vehicle Maintenance Information | C.2 Application Service | One Python process with four modeled child responsibilities |
| F.2.2.1 Validate and Route Owner Requests | C.2.1 Request Routing | `backend/function_f22.py` validation |
| F.2.2.2 Coordinate AI Requests and Responses | C.2.2 AI Coordination | Explicit unavailable boundary; successful external AI remains planned |
| F.2.2.3 Coordinate Confirmed Record Transactions | C.2.3 Record Transaction | Confirmed maintenance-event write |
| F.2.2.4 Calculate Maintenance Summary and Reminders | C.2.4 Maintenance Summary | Stored-history and interval calculation |
| F.2.3 Maintain Vehicle Records | C.3 Vehicle Record Store | SQLite records and saved reminder rules |

Reminders, expense panels and record questions are allocated capabilities, not extra first-level physical assets. A model component need not be an independently deployed server.

## Start and verify

From the repository root, run `py CarCareLog/backend/app.py` on Windows or `python3 CarCareLog/backend/app.py` on macOS/Linux. Open `http://127.0.0.1:8000`. If port 8000 is occupied, choose a free `CARCARE_PORT` before starting and open that port. A package folder named 05_Code_and_Verification is not the repository root; extract its code ZIP first.

In PowerShell, to choose the recording port and an isolated database:

```powershell
$env:CARCARE_PORT = '8772'
$env:CARCARE_DB = Join-Path $PWD 'classroom-demo.db'
py CarCareLog/backend/app.py
```

This creates or reuses that named database; it does not reset an existing recording fixture. Use a separate database for rehearsals. Restore the original rule after UC.2. Stop the service with Ctrl+C.

For tests from the repository root:

```powershell
Push-Location CarCareLog
py -m unittest discover -s tests -v
Pop-Location
```

The existing 27 tests plus three UC.2 tests total 30 cases. Test execution results and CI completion must be read from the release evidence, not inferred from this count.

## Two separate user goals

UC.1 adds one confirmed oil-change event on 2026-10-31 at 52,000 km for USD 89.99. In the recording fixture, three records / USD 359.99 become four / USD 449.98, with record #4 as the reminder source. Routing, confirmed transaction, persistence and summary calculations are shown separately.

UC.2 changes only the saved Oil change rule and its reference. Change the original 8,000 km / six-month example to 1,000 km / one month, save and reload, then restore the original rule and reference. The source record, service ledger and costs remain unchanged. The rule is an IDEF0 control; the saved confirmed history is an input; due limits and status are outputs. The rule-save adapter in app.py is distinct from maintenance-event creation.

## Interval and warning are different

The original sample maintenance interval is **8,000 km OR six calendar months, whichever occurs first**. It produces 60,000 km / 2027-04-30 from the October 31 event. The temporary UC.2 sample produces 53,000 km / 2026-11-30. These are classroom examples; real intervals require the correct vehicle-manual reference.

The separate **Upcoming warning window is 500 international miles (804.672 km) OR 30 days** before a due limit. At a due limit or later, status is Due / overdue. It is not a second maintenance interval. The test observation date is fixed at 2026-11-03; the production app uses today's date, so displayed status changes with time even when the due date remains unchanged.

## Evidence scope

The three new tests cover (1) rule update, fresh API/SQLite read, unchanged ledger, unaffected second vehicle and restoration; (2) invalid update preserving the saved state; and (3) repeated saves retaining one rule. They exercise actual HTTP handlers with isolated test databases. They do not establish browser usability, authenticated owner isolation, successful external AI, seven-day availability or complete requirement acceptance. Those items remain open.
