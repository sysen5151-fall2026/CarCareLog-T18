# Back end (C.2 Application Service and C.3 Vehicle Record Store)

This directory holds the Python service. It uses only the Python standard library and SQLite.

| File | What it does |
| --- | --- |
| [`app.py`](app.py) | HTTP entry point. Serves the front end, routes the API, and stores confirmed records, vehicles and reminder rules in SQLite (C.3). Environment variables: `CARCARE_DB` (database file, default `CarCareLog/data/carcare.db`), `CARCARE_PORT` (default `8000`), and for AI drafting `CARCARE_OLLAMA_MODEL` (set it to `qwen2.5:3b-instruct-q4_K_M`), `CARCARE_OLLAMA_PORT` (default `11434`), and `CARCARE_OLLAMA_TIMEOUT` (seconds, default `60`). |
| [`function_f22.py`](function_f22.py) | F.2.2 coordination: validates and routes owner requests, checks AI receipt drafts against the receipt text (F.2.2.2), commits confirmed record transactions, and calculates the maintenance summary and reminders. |
| [`receipt_runtime.py`](receipt_runtime.py) | Adapter to Ext.2 AI Model Runtime. It pins the model, generation settings, and JSON schema, and asks a local Ollama service on `127.0.0.1` for a receipt-text draft. The draft is never written until the owner confirms it, and a timeout leaves the stored ledger unchanged. |

Drafting is off unless `CARCARE_OLLAMA_MODEL` is set, so the manual path needs no model. The interface contract is [`contracts/api-v1.yaml`](../../contracts/api-v1.yaml).
