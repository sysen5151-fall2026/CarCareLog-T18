# Calendar export for a maintenance reminder

On November 23, 2026, a Chrome session registered a classroom account, loaded the sample vehicle, and selected **Save to calendar (.ics)** on its tire-rotation reminder. The browser downloaded `carcare-reminder-2.ics`. The application returned HTTP 200 with a calendar attachment.

An independent run started the normal single-owner loopback HTTP server on an empty ledger, seeded the sample vehicle and requested the same reminder. Python's `icalendar` 7.3.2 parsed the response into one event and one display alarm. This third-party parser was used only to inspect the output and is not needed to run CarCareLog.

| Property | Decoded value from the single-owner run |
| --- | --- |
| Event | Tire rotation — Demo · 2020 Toyota Corolla |
| Start | December 26, 2026 at 09:00, floating calendar-local time |
| Alert | December 25, 2026 at 09:00, DISPLAY, one day before |
| Identity and timestamp | One occurrence UID and a UTC creation timestamp |

The [calendar regressions](../../CarCareLog/tests/test_calendar_export.py) check stable occurrence identifiers, a same-day alert for a service due tomorrow, invalid and overdue dates, text escaping and UTF-8 line folding. The [account route test](../../CarCareLog/tests/test_owner_site.py) checks valid file download, a signed-out request, a different ledger, and malformed reminder identifiers. The export includes the selected vehicle name and its service. The owner decides which calendar receives it.

The phone's calendar presents the alert after import if its notification settings permit it. No test recorded a physical phone alert. CarCareLog does not send SMS or background push messages. Changed due dates require replacing the previously imported event. The mileage warning still applies when a mileage threshold comes first.
