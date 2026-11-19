# Front end (C.1 Web Interface)

This directory is the browser side of CarCareLog. It implements the owner's side of the OpsCon: Ext.1 Vehicle Owner works through C.1 Web Interface.

| File | What it does |
| --- | --- |
| [`index.html`](index.html) | Page structure: vehicle selector, maintenance timeline, Add record form with **Draft from receipt text** and **Confirm & save**, reminders, cost dashboard, and quick history lookup. |
| [`app.js`](app.js) | Calls the back-end HTTP API (`/api/vehicles`, `/api/demo`, `/api/records`, `/api/receipt-draft`, `/api/receipt-assist`, `/api/dashboard`, `/api/reminders`, `/api/export`, `/api/answer`) and renders the results. An AI draft only fills the form and marks each field found, check, or missing; a record is sent only after the owner selects **Confirm & save**. |
| [`styles.css`](styles.css) | Layout and visual styles. |

The back end serves these files, so there is no separate front-end build step. Start the application as described in the [repository README](../../README.md) and open `http://127.0.0.1:8000`.
