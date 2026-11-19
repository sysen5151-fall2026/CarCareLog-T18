# Clean-machine run (Lab 13.5)

This records a build of CarCareLog from a fresh clone, following only the [README](../README.md).

## Run 1: fresh clone, no model runtime

| Item | Value |
| --- | --- |
| Date | 18 November 2026 |
| Machine | Fresh Ubuntu 24.04.5 LTS container, nothing installed beyond the operating system's Python |
| Python | 3.12.3, started with `-S` so that no site-packages could be imported |
| Source | Fresh `git clone` of branch `lab13-ai-draft` into an empty folder, with an empty home folder and a minimal `PATH` |
| Ollama | Not installed |

Steps, as written in "Reproduce on a clean machine":

```text
$ cd CarCareLog-T18/CarCareLog
$ python3 -m unittest discover -s tests -v
Ran 60 tests ... OK
$ cd ..
$ python3 CarCareLog/tools/smoke_test.py
PASS  page is served with the receipt draft panel
PASS  demo data loads into an empty database
PASS  demo shows 3 records and $359.99
PASS  AI drafting is enabled
PASS  model draft returned in 0.0 s
PASS  draft is not confirmed
PASS  draft did not write a record
      draft: {"service_date": "2026-11-16", "service_item": "Oil change", "category": "Maintenance", "mileage": 52000, "cost": "89.99", "provider": "QuickLube Express"}
      flags: {"service_date": "found", "service_item": "found", "category": "check", "mileage": "found", "cost": "found", "provider": "found"}
PASS  miles converted to 52,000 km; total $89.99
PASS  draft has every required field
PASS  owner Confirm & save writes the record
PASS  dashboard shows 4 records and $449.98
PASS  repeated submit does not duplicate the record
PASS  record persists after a restart
PASS  R2: runtime down returns 503
PASS  R2: manual entry still saves
Smoke test passed with the stub runtime.
$ python3 CarCareLog/tools/evaluate_receipts.py
Ollama is not reachable on 127.0.0.1:11434, or the model is missing.
Start Ollama, then run: ollama pull qwen2.5:3b-instruct-q4_K_M
```

Results: every test and smoke check passed with the standard library alone, and the working tree was still clean afterwards. Without Ollama, the real-model tools stop with a clear instruction instead of a stack trace. The same tests and smoke test also run in CI on Ubuntu, Windows, and macOS (Python 3.12) and on Ubuntu with Python 3.10, 3.11, and 3.13.

The page itself was also driven in a headless browser against this build: paste the sample receipt, **Draft with local AI**, review the marked fields, **Confirm & save**, then the runtime-down and AI-off cases.

## Run 2: team laptop with the pinned model

The Windows team laptop ran Python 3.14.8 with Ollama 0.40.16 and the pinned Qwen2.5 3B Q4_K_M model. The runtime confirmed the pinned weights digest. This is a separate run from the clean Ubuntu container above.

```text
ollama pull qwen2.5:3b-instruct-q4_K_M
python3 CarCareLog/tools/smoke_test.py --real-model
python3 CarCareLog/tools/evaluate_receipts.py
```

The real-model smoke test passed, covering draft review before write, owner confirmation, duplicate-submit handling, persistence after restart, and the unavailable-runtime manual fallback. The [evaluation summary](evidence/lab13-receipt-eval.md) and [raw results](evidence/lab13-receipt-eval.json) record the 20 synthetic receipts, 114 correct fields out of 120, and the request timings. The first request took 23.576 seconds. The warm median was 9.237 seconds and nearest-rank p95 was 15.978 seconds.
