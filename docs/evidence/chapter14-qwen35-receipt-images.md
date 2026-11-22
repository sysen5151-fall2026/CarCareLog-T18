# Local receipt image verification

On November 22, 2026, CarCareLog returned an unconfirmed draft for each of twenty clean, synthetic receipt images. All 120 normalized fields matched their existing labels. The twenty images were rendered from `CarCareLog/data/receipt-samples.jsonl` using Pillow 13.0.0. The application sent the PNG and its extraction instructions to the local model. The text, labels, ideal drafts and identifiers were excluded from each model request. The scorer received the labels after the application reviewed the model output.

| Measure | Observed |
|---|---|
| Model | `qwen3.5:4b`, 4.2B parameters, GGUF Q4_K_M, Ollama 0.40.16 |
| Engine | Windows, CPU inference, Intel Core Ultra 5 125H, loopback service with cloud disabled |
| GGUF manifest SHA-256 | `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` |
| Weights SHA-256 | `a9d0a3e1d8c91732a3812becd31f8d4a8ff57414903f226306069f0437e2ac50` |
| Vision projector SHA-256 | `e56a899b1540860385465756dd308c84417410b94dbc1c380adffd20a921ca60` |
| Draft completion and all-fields accuracy | 20/20 completed, zero timeouts, 20/20 entirely correct |
| Field accuracy | 120/120 across service date, service item, category, normalized mileage, final cost and provider |
| First request, model verifiably unloaded | 29.523 s |
| Subsequent 19 requests | Median 19.196 s; nearest-rank p95 28.458 s |
| Configured timeout | 60 s |

The timer starts immediately before the application adapter call and stops after its six-field review. It excludes fixture rendering, choosing a file, reading the review screen and saving. Missing values specified by the labels are scored by the same rule as the text benchmark. No wrong field occurred in this image run, so an error-detection rate cannot be estimated. The pilot still requires the owner to verify every image-derived value. These clean PNGs cover the original synthetic texts. They do not measure physical camera blur, glare, skew, handwriting or first-time user performance. The earlier Qwen2.5 text-only runs have different model and input conditions.

A separate product HTTP trial used the R01 PNG and an isolated SQLite database. All nine checks passed, including no write before confirmation, rejection of an unconfirmed submission, a single row after simulated owner confirmation and retry, restart persistence, and absence of the image or its base64 representation in the resulting database. The record and dashboard were read through the normal application endpoints. This was an automated operator, not a representative-owner session.

With Pillow 13.0.0 available, run the following from the repository root. Start the local Ollama service before executing the commands.

```powershell
ollama pull qwen3.5:4b
python CarCareLog/tools/evaluate_receipt_images.py --as-of 2026-11-22 --output-dir .local-image-check
python CarCareLog/tools/verify_image_workflow.py --repo . --fixture .local-image-check/fixtures/R01.png --output .local-image-check/workflow.json
```

The measured [per-receipt results](chapter14-qwen35-receipt-images.json) include the exact fixture image hashes. The [HTTP workflow record](chapter14-qwen35-image-workflow.json) lists calls and observed outcomes. The [November 22 text baseline](lab13-receipt-comparison-local.json) retains the previously tested Qwen2.5 results.
