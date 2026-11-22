# CarCareLog Product Risk Register

The team supplied the likelihood and the cost, schedule and technical impact ratings for the five system risks, using the Lab 13 results as evidence. No rating is above 3. The overall impact is the mean of the three impact ratings, rounded to the nearest integer. The overall level is read from the [native Innoslate matrix](https://cloud.innoslate.com/cornell/p/746/diagrams/risk/318543) where the likelihood row meets the overall impact column. Green is Low, yellow is Medium and red is High. The ratings are ordinal engineering judgments, so they are not multiplied. [Lab Manual §12](https://claude.ai/artifact/6uswv5JmPsGk8doEDJMQ7v#lm-12-risk-assessment).

| Rating | Likelihood during the pilot | Cost impact | Schedule impact | Technical impact |
| --- | --- | --- | --- | --- |
| 1 | Rare (about 10%) | Up to $10 | Up to half a day | Negligible. Local recovery. |
| 2 | Unlikely but credible (about 30%) | Above $10 through $25 | Above half a day through 1 day | Minor. A fallback is available. |
| 3 | May occur (about 50%) | Above $25 through $50 | Above 1 through 3 days | Moderate. Part of a workflow is lost. |
| 4 | Likely (about 70%) | Above $50 through $100 | Above 3 through 7 days | Serious. The core workflow is impaired. |
| 5 | Expected repeatedly (about 90%) | Above $100 | Above 7 days | Critical. Core operation or trustworthy data is lost. |

Cost impact counts team labor at $25 per hour plus any service charges. In Innoslate the likelihood and overall impact are stored as Probability and Consequence percentages (10, 30, 50, 70 and 90% for levels 1 to 5).

## Identification and assessment

| Risk and affected behavior | Type and life cycle phase | Model trace | Likelihood | Cost | Schedule | Technical | Overall impact | Matrix cell and overall level |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| [R1](https://cloud.innoslate.com/cornell/p/746/database/entity/318550) If a well-formed draft contains a wrong value, the owner may confirm and save a wrong date, mileage, service or cost. | Technical integrity, design and verification | UC.1, UC.4, F.2.2.2 and F.2.2.3 | 3 | 1 | 2 | 3 | 2 | Medium × Minor, **Medium (yellow)** |
| [R2](https://cloud.innoslate.com/cornell/p/746/database/entity/318551) If the AI runtime is slow, not running or times out, the owner gets no draft and must enter the record by hand. | Availability, integration and operation | F.2.2.2, C.2.2, IC-03, FCS.2.1.2 | 3 | 2 | 3 | 3 | 3 | Medium × Moderate, **Medium (yellow)** |
| [R3](https://cloud.innoslate.com/cornell/p/746/database/entity/318552) If receipt text contains instructions or misleading numbers, the model may propose a value that is not the real total, date or service. | Input integrity, design and verification | UC.1, F.2.2.2, IC-03 | 2 | 1 | 2 | 2 | 2 | Medium Low × Minor, Low (green) |
| [R4](https://cloud.innoslate.com/cornell/p/746/database/entity/318553) If receipt or vehicle data is sent off the owner's computer, the pilot breaks its data boundary. | Privacy, design and operation | F.2.2.2, C.2.2, Ext.2, IC-03 | 1 | 2 | 3 | 3 | 3 | Low × Moderate, Low (green) |
| [R5](https://cloud.innoslate.com/cornell/p/746/database/entity/318554) If a confirmed record is not saved or is saved to the wrong vehicle, the ledger and reminders are wrong. | Data integrity, integration and operation | UC.1, F.2.2.3, C.3 | 2 | 2 | 3 | 3 | 3 | Medium Low × Moderate, Low (green) |

Basis for the ratings:

- **R1.** In the Lab 13 evaluation, 3 of 20 drafts had at least one wrong value (6 of 120 values). All 6 were flagged for the owner, which keeps the likelihood at 3.
- **R2.** On November 19 the cold first request took 23.576 s and the warm p95 was 15.978 s against a 60 s timeout, on a laptop without a GPU. A repeat run on November 22 was about twice as fast, so timing depends on the laptop's load. The same day the comparison run stopped once because the Ollama app had not been started.
- **R3.** The one labeled receipt with an injected instruction (R09) was handled correctly, but it is the only case of its kind.
- **R4.** SA.A uses only the loopback address, and the hosted model is not wired into the application.
- **R5.** Confirmed writes pass the persistence tests, but the draft page adds a vehicle selection step.

## Response, monitoring and control

Risks are listed in priority order: by matrix level, then likelihood, then overall impact. The owner reviews each risk on the schedule shown, records new findings in the linked Innoslate entity, then checks the matrix and this register so they agree.

| Priority | Risk | Strategy and response | Indicator and trigger for action | Review | Risk owner | Status |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | R2 (Medium) | **Mitigate.** On runtime failure or a 60 s timeout, return HTTP 503 with no draft and leave the manual form available (FCS.2.1.2). Keep the model loaded for 30 minutes after use. The page says when drafting is off. | Timeouts, failed requests, cold-start time and warm p95 in each labeled run. Trigger: any timeout, a warm p95 above 30 s, a changed ledger row after a failure, or a failed manual save. Action: block release and investigate the runtime. | Each runtime or model change, before release, and weekly during the pilot | Zeyu Zhang | Open. [Timeout regression](../CarCareLog/tests/test_receipt_runtime.py) and [smoke test](../CarCareLog/tools/smoke_test.py) cover the fallback. |
| 2 | R1 (Medium) | **Mitigate.** F.2.2.2 checks each drafted value against the receipt text and marks it found, check or missing. Nothing is saved until the owner confirms (F.2.2.3). | Wrong values, and wrong values shown as found, in each labeled run. Trigger: any wrong value shown as found, or field accuracy below 90%. Action: fix the checks or prompt before the next demo. | Every labeled run and every model or prompt change | Zhihao Chen | Open. 6 of 6 wrong values flagged in Lab 13. [Review tests](../CarCareLog/tests/test_receipt_review.py) cover the checks. |
| 3 | R5 (Low) | **Mitigate.** Bind each confirmed write to the selected vehicle, save it in one C.3 transaction and check the record after reload. | Selected-vehicle and persistence regression results. Trigger: a missing or misfiled row. Action: block release and review the transaction path. | Each storage or page change and before release | Ruitong Geng | Open. [Function tests](../CarCareLog/tests/test_functional_requirements.py) cover the transaction. |
| 4 | R3 (Low) | **Mitigate.** Limit receipt text to 4,000 characters, send it as data inside the prompt and apply the same schema and checks. A cost counts as found only when it follows a total label. | Results on R09 and the distractor receipts. Trigger: any value taken from an injected instruction is shown as found. Action: open a defect and stop promoting that model or prompt. | Each prompt or model change | Lian Chen | Open. [Labeled receipts](../CarCareLog/data/receipt-samples.jsonl) include the case; R09 handled correctly in Lab 13. |
| 5 | R4 (Low) | **Avoid.** Keep IC-03 on the loopback address, run Ollama in local-only mode and send only the receipt text. SA.B stays out of the application. | Daemon bind address and observed network destinations. Trigger: any off-host receipt traffic. Action: turn drafting off and start a privacy review. | Before the pilot and after any configuration change | Yunyi Zhao | Open. App boundary inspected. Daemon egress check pending. |

Schema drift (P1) is tracked under R1 and R2 through IC-03. Require contract regression and malformed-response tests before changing models. Dependency abandonment (P2) is tracked under R2 through Ext.2. Check release and support status at each planned upgrade, and keep manual entry available if the runtime cannot respond.

The R2 timeout fixture checks HTTP 503, an unchanged ledger and a subsequent successful manual save. Runtime performance is measured separately by [the labeled receipt evaluation](../CarCareLog/tools/evaluate_receipts.py) and [the paired runtime comparison](../CarCareLog/tools/compare_receipt_runtimes.py).
