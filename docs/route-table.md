# Product entry points and use cases

| Product entry | Use case / path | HTTP operation | Function | Result |
|---|---|---|---|---|
| Dashboard: Add record, then Confirm & save | UC.1 Manage Maintenance Records, manual-entry alternative | POST /api/records | F.2.2.1 and F.2.2.3 | Reject invalid/unconfirmed request or return committed record ID |
| Dashboard refresh after save | UC.1 updated history and reminders | GET /api/dashboard?vehicle_id={id} | F.2.2.4, with C.3 record retrieval | Selected vehicle records, costs and reminders |
| Record Edit, then Confirm & save | UC.1 correction alternative | PUT /api/records/{id} | Manual transaction adapter | Confirmed corrected fields |
| Receipt upload / generative question | Planned receipt-assisted UC.1 path | No implemented external-AI route | F.2.2.2 | Explicitly outside current demo |

The UI passes `owner_confirmed: true` only through the explicit Confirm & save form submission. This is a workflow control, not an identity credential. The app binds to localhost and has no owner accounts.
