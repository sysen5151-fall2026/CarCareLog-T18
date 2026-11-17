# CarCareLog Application

The [repository README](../README.md) has the classroom demonstration, implementation status, and setup instructions. This directory contains the browser UI, Python service, and automated checks.

- [`frontend/`](frontend/) contains the browser interface and JavaScript API calls.
- [`backend/`](backend/) contains the HTTP entry point, SQLite persistence, F.2.2 coordination, and the optional local receipt-text adapter.
- [`tests/`](tests/) verifies manual records, reminders, contract behavior, and receipt-runtime fallback.

From this directory, run `py -3 backend/app.py` on Windows or `python3 backend/app.py` on macOS and Linux. Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The default database is `data/carcare.db`. Follow the repository README to use an isolated demonstration database.
