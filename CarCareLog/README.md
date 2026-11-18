# CarCareLog Application

The [repository README](../README.md) has the classroom demonstration, implementation status, and setup instructions. This directory contains the browser UI, Python service, and automated checks.

- [`frontend/`](frontend/) contains the browser interface and JavaScript API calls.
- [`backend/`](backend/) contains the HTTP entry point, SQLite persistence, F.2.2 coordination, and the optional local receipt-text adapter.
- [`tests/`](tests/) verifies manual records, reminders, contract behavior, receipt drafts and their checks, and the runtime fallback.
- [`tools/`](tools/) holds the end-to-end smoke test, the labeled-receipt evaluation, and the Chapter 10 measurement script.
- [`data/`](data/) holds the synthetic labeled receipts and the demonstration receipt. The default database file is also created here.

From this directory, run `py -3 backend/app.py` on Windows or `python3 backend/app.py` on macOS and Linux. Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The default database is `data/carcare.db`. Follow the repository README to use an isolated demonstration database.
