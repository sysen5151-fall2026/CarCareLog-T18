# Chapter 10 Modeling and Simulation

This page connects Team 18’s Modeling and Simulation report to the CarCareLog implementation. The comparison covers UC.1 manual record entry. UC.2 reminder status is an output of the refreshed dashboard. Editing a rule remains a separate UC.2 action.

## Scenarios

| Scenario | Innoslate | Local product path |
| --- | --- | --- |
| **B. Separate refresh (default)** | [Action](https://cloud.innoslate.com/cornell/p/746/diagrams/action/308529) · [Sequence](https://cloud.innoslate.com/cornell/p/746/diagrams/sequence/308529) · [Monte Carlo result](https://cloud.innoslate.com/cornell/p/746/database/entity/308635) | On the default site, confirm a new record. The browser posts to `/api/records`, fetches the vehicle list, and fetches the selected dashboard. |
| **A. Bundled response (opt-in)** | [Action](https://cloud.innoslate.com/cornell/p/746/diagrams/action/308559) · [Sequence](https://cloud.innoslate.com/cornell/p/746/diagrams/sequence/308559) · [Monte Carlo result](https://cloud.innoslate.com/cornell/p/746/database/entity/308636) | Open `http://localhost:8000/?save=bundled`. A confirmed new record posts to `/api/records?include=dashboard`. On success the browser can render the returned dashboard without two extra requests. |

Both paths require the owner’s confirmation. The service commits the record to SQLite before it reads the dashboard. If the optional read fails, the save still returns a stored ID and the browser can use the ordinary refresh. Replaying the same confirmed create request with the same per-vehicle operation ID returns the stored record ID without a duplicate write. A different payload using that ID is rejected.

## Allocation and tests

| Model element | Implementation and selected evidence |
| --- | --- |
| Ext.1 Vehicle Owner and C.1 Web Interface | The [website](../CarCareLog/frontend/app.js) collects the record and presents the confirmed result. Owner entry, review and browser rendering need separate timing measurements. |
| F.2.2.1 / C.2.1, Validate and Route Owner Requests | [Validation and routing](../CarCareLog/backend/function_f22.py) check vehicle and inputs. See ASR 1.4.1 and SRD 1.4.1.2 tests in the [traceability matrix](traceability.md). |
| F.2.2.3 / C.2.3, Coordinate Confirmed Record Transactions, using C.3 Vehicle Record Store | The [service adapter](../CarCareLog/backend/app.py) commits to C.3 before acknowledgment. ASR 1.4.3 tests stored ID and confirmation. Regression tests cover replay, deletion and a failed dashboard read after commit. |
| F.2.2.4 / C.2.4, Calculate Maintenance Summary and Reminders | The same calculation prepares both dashboards. A regression test checks the entire bundled result against a fresh dashboard read, including the reminder’s source record. |

See the [HTTP contract](../contracts/api-v1.yaml) and [route table](route-table.md) for the exact routes and payloads.

## Evidence in the report

The report’s 100 Innoslate Monte Carlo runs per scenario averaged 24.89 s (B) and 21.70 s (A). The independent draws for the owner stages account for most of the variation, so these means do not isolate the implementation’s effect.

In the 40 paired loopback HTTP trials, the mean was 35.61 ms for B and 17.53 ms for A. Every pair returned equal dashboard data, and every trial persisted its confirmed record. This measures request initiation through response decoding. It excludes owner entry, owner review and browser rendering.

To run a new local comparison with synthetic data, from the repository root use:

```powershell
py CarCareLog/tools/measure_product.py --output .\chapter10-bench
```

The harness creates an isolated database per trial, performs one warm-up pair, alternates the measured order, and writes a new CSV and run note. Timings vary by machine. The original measurements are in the evidence package accompanying the course report.

| Timing requirement | Status |
| --- | --- |
| [SRD 2.1.3](https://cloud.innoslate.com/cornell/p/746/database/entity/263266) / SR05 | Open. Receipt-assisted usability needs first-time owner testing against the 180-second criterion. |
| [SRD 2.1.2](https://cloud.innoslate.com/cornell/p/746/database/entity/263265) / SR14 | Open. The 99% target requires a seven-day pilot. |
| [SRD 2.1.4](https://cloud.innoslate.com/cornell/p/746/database/entity/263267) / SR18 | Partial evidence. The isolated restore passed SQLite integrity and dashboard checks. The 24-hour recovery-point age still needs verification. |
| [SR08](https://cloud.innoslate.com/cornell/p/746/database/entity/245392) | The Upcoming warning is within 500 miles (804.672 km) or 30 days of a due threshold. The classroom maintenance interval is a separate example of 8,000 km or six months. |
