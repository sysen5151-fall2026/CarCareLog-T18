# CarCareLog

Cornell SYSEN 5151 - Team 18

Lian Chen, Ruitong Geng, Zhihao Chen, Yunyi Zhao, Zeyu Zhang

## About the project

CarCareLog helps vehicle owners keep their maintenance and repair history in one place. Owners can record completed work, check spending and see when a configured service is due. The project addresses a common problem: receipts and service details are scattered across paper copies, emails and personal notes.

Our Innoslate model also includes receipt-assisted entry and questions answered from vehicle records or manual information. This repository contains the first local prototype. It currently supports manual entry and two predefined history questions. Receipt processing and external AI calls are still to be added.

## System boundary

The system of interest is the CarCareLog application. The final physical model decomposes C.0 CarCareLog System into C.1 Web Interface, C.2 Application Service and C.3 Vehicle Record Store. These perform F.2.1 presentation, F.2.2 coordination and F.2.3 record maintenance. C.2 further contains C.2.1 Request Routing, C.2.2 AI Coordination, C.2.3 Record Transaction and C.2.4 Maintenance Summary. Reminder calculation, expense views and record questions are capabilities allocated to those components, not additional first-level assets. The four C.2 responsibilities are modules in one Python service; C.3 uses SQLite. External AI remains planned.

The owner supplies vehicle details, current mileage, service costs and maintenance intervals. CarCareLog stores and uses that information; it does not read mileage from the vehicle or estimate repair prices. Mechanical diagnosis, repair work and booking appointments are outside the project scope. Repair-shop and buyer portals are also outside the initial scope.

## External actors and systems

The following names match the system context model:

| Model entity | Interaction with CarCareLog |
| --- | --- |
| Vehicle Owner | Enters and confirms records, updates mileage, reviews reminders and expenses, asks questions and exports history. |
| Service Provider | Supplies service receipts and information. In the initial workflow, the owner brings this information into CarCareLog; the provider does not need a CarCareLog account or a direct software connection. |
| AI Model Runtime | Planned external service for proposing receipt fields and answering questions from supplied records or manual information. This prototype makes no requests to it and needs no API key. |

The application operator and development team are support stakeholders. The AI service provider representative is a stakeholder associated with the external runtime, rather than the runtime itself.

## Use cases and current coverage

These are the four use cases in our model:

| Use case | Current prototype |
| --- | --- |
| UC.1 Manage Maintenance Records | Add, edit, delete and search confirmed records for a selected vehicle; export history to CSV. Receipt upload and AI field proposals are pending. |
| UC.2 Review Maintenance Reminders | Set mileage or month intervals with a manual reference, then review the calculated status. Changes to mileage or service history update the reminders. |
| UC.3 Review Maintenance Expenses | Review total recorded costs and monthly spending by Maintenance or Repair category. Costs come from saved records. |
| UC.4 Ask Questions About Vehicle Records | Look up the last recorded oil change or total recorded cost, with source record IDs. Free-text AI questions and manual-based answers are pending. |

The working path is: select a vehicle, enter and confirm a service record, save it, then review the updated history, expenses and reminders. This covers the manual-entry part of UC.1. The modeled receipt-to-AI-to-owner-confirmation path is not implemented yet.

Requirement IDs and remaining work are recorded in [MVP scope](CarCareLog/docs/MVP_SCOPE.md) and [model traceability](docs/traceability.md). For example, EN01 leads to SR01 and SR02, which concern record management and retrieval under UC.1. The forms and API operations in this repository exercise that part of the model. Full requirement acceptance has not been established by this prototype.

## Chapter 10 modeling and simulation

The default site uses scenario B, the three-exchange save and refresh flow. To try scenario A on the same prototype, open [http://localhost:8000/?save=bundled](http://localhost:8000/?save=bundled) and confirm a **new** manual record. The dashboard can return with the save confirmation after the write commits. The [Chapter 10 model and evidence map](docs/modeling-and-simulation.md) links both scenarios to the Innoslate diagrams, requirement IDs and tests. The recorded PMC2 and Friday walkthroughs use the historical baseline revision `5aca599`.

## Run the application

You need Python 3.10 or later and a web browser. No extra Python packages are required.

1. Check out `codex/milestone2-video`, or extract the current packaged source ZIP. Open the repository root, containing `CarCareLog/`, `docs/` and `contracts/`.
2. From the repository root, run the application:

**Windows PowerShell**

```powershell
py CarCareLog/backend/app.py
```

**macOS or Linux**

```bash
python3 CarCareLog/backend/app.py
```

3. Keep the terminal open and visit [http://127.0.0.1:8000](http://127.0.0.1:8000).
4. Click **Add vehicle**, or use **Load demo data** only with an empty database. For the recorded UC.1 + UC.2 fixture, use `docs/DEMO_RELEASE.md`; do not substitute fresh sample dates for the documented recording.

If your terminal is already inside `CarCareLog/`, use `py backend/app.py` on Windows or `python3 backend/app.py` on macOS/Linux.

Press Ctrl+C in the terminal to stop the application. Saved records remain available when you start it again. The address is local to the computer running the backend; another computer must start its own copy to use that address.

## Data and prototype limits

From the repository root, data is stored in `CarCareLog/data/carcare.db` using SQLite. This file is excluded from Git. To back up the data, stop the application and copy the database file. Keep it when moving the project to another folder. CSV export includes confirmed service records, but is not a full database backup.

Mileage is currently entered in kilometers and costs in USD. The owner enters the interval and its vehicle-manual reference; the application does not retrieve or verify the manual. Demo intervals are examples. Reminders appear on the page, with no email or phone notifications.

The upcoming-service window is 30 days OR 500 international miles (804.672 km). Distance remains stored in km. Exact, below and above distance/time boundary tests retain this earlier requirements-document baseline; native Innoslate requirement statements are unchanged.

The server listens on `127.0.0.1` and is intended for one local user. Owner login and access control, receipt processing, external AI integration and automatic recovery are future work. Availability and usability targets still need validation.

Optional settings are `CARCARE_PORT` (default: `8000`) and `CARCARE_DB` (database path).

## Repository files

| File | Purpose |
| --- | --- |
| [`CarCareLog/backend/app.py`](CarCareLog/backend/app.py) | HTTP API, SQLite storage and scenario instrumentation |
| [`CarCareLog/backend/function_f22.py`](CarCareLog/backend/function_f22.py) | F.2.2 routing, transaction and summary logic |
| [`CarCareLog/frontend/app.js`](CarCareLog/frontend/app.js) | Forms, API calls and dashboard updates |
| [`CarCareLog/tests/test_app.py`](CarCareLog/tests/test_app.py) | Backend, API and Chapter 10 regression checks |
| [`contracts/api-v1.yaml`](contracts/api-v1.yaml) | Modeled internal adapters and local HTTP interface |

## Run the checks

From the repository root, run:

**Windows**

```bat
Push-Location CarCareLog
py -m unittest discover -s tests -v
Pop-Location
```

**macOS or Linux**

```bash
(cd CarCareLog && python3 -m unittest discover -s tests -v)
```

The checks use a temporary database and do not change your saved vehicle records.


## PMC2 TA4 revision 3 November 2026

Use branch `codex/milestone2-video`, local port 8772 and the matching packaged source. Read `docs/traceability.md`, `docs/requirements-baseline.json`, `docs/route-table.md` and `contracts/api-v1.yaml` from the repository root. Four localhost internal contract endpoints link F.2.2.1-F.2.2.4 to typed inputs and outputs. External AI is unavailable and returns 503; successful OCR, generative AI and owner authentication remain planned. Native model status and system acceptance remain open. The latest test log and CI receipt, rather than an older passing run, establish the revision tested.

## PMC2 UC 1 and UC 2 release

Release identifier: `PMC2-UC2-20261103`. The packaged `RELEASE_MANIFEST.json` records the exact Git commit, test count and CI evidence. Use that commit consistently for the code ZIP, slides, video and instructor guide. The classroom route remains UC.1 Manage Maintenance Records followed by UC.2 Review Maintenance Reminders.

The original classroom service interval is 8,000 km OR six calendar months, whichever comes first. The temporary UC.2 demonstration rule is 1,000 km OR one calendar month and is restored afterward. These are example intervals with classroom references, not manufacturer recommendations. The separate Upcoming warning window is 500 international miles (804.672 km) OR 30 days before a due limit. At a due limit or later, status is Due / overdue. See `docs/DEMO_RELEASE.md`.
