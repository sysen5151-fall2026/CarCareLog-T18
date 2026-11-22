# Lab 13 receipt comparison status on November 22, 2026

The model-access check for GPT-6.1 Sol returned HTTP 200 at 20:50:34 UTC. The first synthetic receipt, R01, received HTTP 429 from the Responses API and the evaluation stopped. A diagnostic retry of the same receipt at 20:51:26 UTC also returned HTTP 429, with type `insufficient_quota` and code `credit_balance_exhausted`. Neither request produced a draft. [Service status record](lab13-receipt-comparison-status.json)

| Measure | SA.A · Ollama Qwen2.5 3B | SA.B · GPT-6.1 Sol |
|---|---:|---|
| Receipt drafts returned | 20 of 20 | 0 from R01 (R02–R20 untested) |
| Correct fields | 114 of 120 (95.0%) | No fields available to score |
| Receipts with all six fields correct | 17 of 20 | Unmeasured |
| First successful response | 15.263 s | Unmeasured |
| Warm median / nearest-rank p95 | 7.270 s / 7.831 s (19 requests) | Unmeasured |
| E5 response-time value under ADR 011 | 0.899466 | Unmeasured |

SA.A reuses the November 22 Ollama run on the same 20 labeled synthetic receipts. Six fields per receipt were checked. E5 uses the warm p95 and awards 1 at 2 seconds and 0 at 60 seconds, with linear interpolation. The elapsed time for a rejected API request cannot measure time to a completed draft. **The measured E5 ranking is open.** [Local measurements and score calculation](lab13-receipt-local-score-audit.md)

**Overall selection under the report's pilot assumptions.** SA.A scores 0.890171. The report assigns one off-host destination to SA.B, assumes both manual-continuity checks pass, and uses planned first-year costs of $75.08 for SA.A and $76.40 for SA.B. At these values, SA.B scores at most 0.588020 even with perfect field accuracy and an E5 value of 1. The weighted model therefore favors SA.A for every possible hosted accuracy and response-time result under these assumptions. [ADR 011](../adr-011-receipt-runtime.md) · [Calculation and swing points](lab13-receipt-local-score-audit.md)

**Completing the comparison.** When the API project has sufficient credit, run the hosted evaluator with the same fixture, then render the paired report from the two JSON captures. The `hosted` command below uses the operator's configured environment. The `report` command checks that the two captures have the same receipt-file digest. [Comparison tool](../../CarCareLog/tools/compare_receipt_runtimes.py)

```powershell
py -3 CarCareLog/tools/compare_receipt_runtimes.py hosted
py -3 CarCareLog/tools/compare_receipt_runtimes.py report
```
