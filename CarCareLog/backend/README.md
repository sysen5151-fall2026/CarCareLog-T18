# Back end (C.2 Application Service and C.3 Vehicle Record Store)

This directory holds the Python service. It uses only the Python standard library and SQLite.

| File | What it does |
| --- | --- |
| [`app.py`](app.py) | HTTP entry point. Serves the front end, routes the API, and stores confirmed records, vehicles and reminder rules in SQLite (C.3). Environment variables: `CARCARE_DB` (database file, default `CarCareLog/data/carcare.db`), `CARCARE_PORT` (default `8000`) and the optional `CARCARE_OLLAMA_MODEL`. |
| [`function_f22.py`](function_f22.py) | F.2.2 coordination: validates and routes owner requests, commits confirmed record transactions, and calculates the maintenance summary and reminders. |
| [`receipt_runtime.py`](receipt_runtime.py) | Optional adapter to Ext.2 AI Model Runtime. It asks a local Ollama service for a receipt-text draft. The draft is never written until the owner confirms it, and a timeout leaves the stored ledger unchanged. |

The adapter is off unless `CARCARE_OLLAMA_MODEL` is set, so the manual demo needs no model. The interface contract is [`contracts/api-v1.yaml`](../../contracts/api-v1.yaml).
