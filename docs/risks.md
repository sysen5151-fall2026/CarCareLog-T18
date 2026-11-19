# CarCareLog Product Risk Register

The team supplied the likelihood and the cost, schedule and technical impact ratings for the five system risks. Compute the overall impact as the mean of the three impact ratings, rounded to the nearest integer. Read the overall level from the [native Innoslate matrix](https://cloud.innoslate.com/cornell/p/746/diagrams/risk/318543) where the likelihood row meets the overall impact column. Green is Low, yellow is Medium and red is High. The ratings are ordinal engineering judgments. [Lab Manual §12](https://claude.ai/artifact/6uswv5JmPsGk8doEDJMQ7v#lm-12-risk-assessment).

| Rating | Likelihood during the pilot | Cost impact | Schedule impact | Technical impact |
| --- | --- | --- | --- | --- |
| 1 | Rare | Up to $10 | Up to half a day | Negligible. Local recovery. |
| 2 | Unlikely but credible | Above $10 through $25 | Above half a day through 1 day | Minor. A fallback is available. |
| 3 | May occur | Above $25 through $50 | Above 1 through 3 days | Moderate. Part of a workflow is lost. |
| 4 | Likely | Above $50 through $100 | Above 3 through 7 days | Serious. The core workflow is impaired. |
| 5 | Expected repeatedly | Above $100 | Above 7 days | Critical. Core operation or trustworthy data is lost. |

## Identification and assessment

| Risk and affected behavior | Type and life cycle phase | Model trace | Likelihood | Cost | Schedule | Technical | Overall impact | Matrix cell and overall level |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| [R2](https://cloud.innoslate.com/cornell/p/746/database/entity/318551) The AI runtime is late or unavailable, interrupting the owner's receipt draft. | Availability, integration and operation | F.2.2.2, C.2.2, IC-03, FCS.2.1.2 | 1 | 2 | 2 | 2 | 2 | Low likelihood × Minor impact, **Low (green)** |
| [R1](https://cloud.innoslate.com/cornell/p/746/database/entity/318550) A well-formed draft contains a wrong value and could mislead the owner. | Technical integrity, design and verification | UC.1, UC.4, F.2.2.2 and F.2.2.3 | 1 | 1 | 1 | 1 | 1 | Low likelihood × Negligible impact, Low (green) |
| [R3](https://cloud.innoslate.com/cornell/p/746/database/entity/318552) Untrusted receipt text distorts the model proposal. | Input integrity, design and verification | UC.1, F.2.2.2, IC-03 | 1 | 1 | 1 | 1 | 1 | Low likelihood × Negligible impact, Low (green) |
| [R4](https://cloud.innoslate.com/cornell/p/746/database/entity/318553) Receipt or vehicle data reaches an unintended destination. | Privacy, design and operation | F.2.2.2, C.2.2, Ext.2, IC-03 | 1 | 1 | 1 | 1 | 1 | Low likelihood × Negligible impact, Low (green) |
| [R5](https://cloud.innoslate.com/cornell/p/746/database/entity/318554) A confirmed event is lost or assigned to the wrong vehicle, affecting the ledger and reminders. | Data integrity, integration and operation | UC.1, F.2.2.3, C.3 | 1 | 1 | 1 | 1 | 1 | Low likelihood × Negligible impact, Low (green) |

R2 is the top pilot risk because it has the highest impact at the shared likelihood rating. R1, R3, R4 and R5 have equal priority under the current ratings.

## Response, monitoring and control

The owner column lists the team member responsible for each risk. Review the evidence at integration, after changes affecting the risk and before release. Record new findings and actions in the linked risk entity, then review the rating and matrix cell together.

| Risk | Strategy and response | Monitoring and trigger | Risk owner | Status |
| --- | --- | --- | --- | --- |
| R2 | **Mitigate.** On runtime failure, return HTTP 503 with no draft and leave the manual form available. The default transport timeout is 60 seconds. | Track latency, timeout count and manual fallback success. Any changed ledger row, unexpected response or failed manual save blocks release. | Zeyu Zhang | Open. [Timeout regression](../CarCareLog/tests/test_receipt_runtime.py) and [smoke test](../CarCareLog/tools/smoke_test.py) cover the fallback. |
| R1 | **Mitigate.** F.2.2.2 checks each drafted value against receipt text and marks values needing review. The owner confirms before any write. | Review wrong values and which receive flags in each labeled run or model change. An unconfirmed write blocks release. Investigate any wrong value shown as found. | Zhihao Chen | Open. [Review tests](../CarCareLog/tests/test_receipt_review.py) cover the checks. |
| R3 | **Mitigate.** Limit receipt text to 4,000 characters, send it as data and apply the same schema and review rules. | Retest the unlabeled-instruction failure pattern on prompt and model changes using labeled sample R09. Unexpected acceptance opens a defect and blocks promotion until reviewed. | Lian Chen | Open. [Labeled receipts](../CarCareLog/data/receipt-samples.jsonl) include the case. |
| R4 | **Avoid.** Keep pilot transport on loopback, configure the daemon for local-only operation and send only the receipt text. | Review daemon settings and observed destinations before the pilot and after configuration changes. Off-host receipt traffic pauses drafting and triggers a privacy review. | Yunyi Zhao | Open. App boundary inspected. Daemon egress verification remains pending. |
| R5 | **Mitigate.** Bind confirmed writes to the selected vehicle and verify persistence after reload. | Run selected-vehicle and persistence regressions on storage changes and before release. A missing or misattributed row blocks release. | Ruitong Geng | Open. [Function tests](../CarCareLog/tests/test_functional_requirements.py) cover transaction behavior. |

Schema drift (P1) is tracked under R1 and R2 through IC-03. Require contract regression and malformed-response tests before changing models. Dependency abandonment (P2) is tracked under R2 through Ext.2. Check release and support status at each planned upgrade, and keep manual entry available if the runtime cannot respond.

The R2 timeout fixture checks HTTP 503, an unchanged ledger and a subsequent successful manual save. Provider performance is evaluated separately by [the labeled receipt evaluation](../CarCareLog/tools/evaluate_receipts.py).
