# November 22 local baseline for the Lab 13 receipt comparison

SA.A completed all 20 synthetic receipts with the pinned Ollama model `qwen2.5:3b-instruct-q4_K_M`. The run finished at 12:33:25 p.m. Eastern on November 22, 2026. The table below was recalculated from the 20 individual request records in commit `c28fae0`. The labeled receipt file has SHA-256 `a8da46ad220cae726f1216e433f3fcbba701e36c7ad6e29dc20b0ad2834b933f` after normalizing line endings. [November 22 measurements](https://github.com/sysen5151-fall2026/CarCareLog-T18/blob/c28fae060860da4574f4b45cce61bfd0a330dbdc/docs/evidence/lab13-receipt-comparison-local.json) · [Labeled receipts](../../CarCareLog/data/receipt-samples.jsonl)

| Measure | November 22 result |
|---|---:|
| Correct fields, across all six fields per receipt | 114/120 (95.0%) |
| Receipts with all six fields correct | 17/20 (85.0%) |
| Incorrect fields flagged for review / shown as found | 6 / 0 |
| First request | 15.263 s |
| Warm median over R02–R20 | 7.270 s |
| Warm nearest-rank p95 over R02–R20 | 7.831 s |

**E5 is 0.899466.** With 19 successful warm requests, the nearest-rank 95th percentile is the 19th sorted duration. E5 earns 1 at 2 seconds or faster and 0 at 60 seconds or slower. Between these anchors the score is `(60 − p95) / 58`. The archived November 22 JSON includes an earlier derived `v5` value of 0.0. Reapplying the current rule to the recorded 7.831 seconds gives `(60 − 7.831) / 58`. The November 19 run had its own p95 of 15.978 seconds and E5 of 0.759. [Scoring implementation](../../CarCareLog/tools/compare_receipt_runtimes.py) · [November 19 evaluation](lab13-receipt-eval.md)

**SA.A's overall value is 0.890171** using the November 22 measurements and the report's original pilot planning assumptions. The swing points for E1 through E5 are 100, 26, 51, 75 and 51, totaling 303. At a planned first-year cost of $75.08 against an $80 budget, SA.A's E2 value is 0.0615. SA.A has zero off-host application destinations (E1 = 1) and passes both failure-path checks (E3 = 1). Its weighted value is `(100 + 26 × 0.0615 + 51 + 75 × 0.95 + 51 × 0.899465517) / 303`. The November 19 measurements give 0.866528 under the same assumptions. [ADR 011](../adr-011-receipt-runtime.md)

For the hosted comparison, use the same sample digest and exclude the first request when computing warm p95. SA.B leads **on E5 alone** if its observed warm p95 is below 7.831 seconds and ties at exactly 7.831 seconds. Under the report's original $76.40 hosted cost estimate, one off-host destination and assumed two successful manual-continuity checks, its **overall** value has an upper bound of 0.588020 even if accuracy and E5 both reach 1. This bound is a planning calculation. An observed SA.B E5 value and a measured ordering on latency require a completed hosted run.
