# Local account demonstration on November 23

Reviewers can run `python run_demo.py --accounts` on their own computers. The optional entry point uses a separate SQLite ledger for each local account. The original single-owner entry point remains available.

## Browser observation

A Chrome session opened the application's sign-in form, registered a temporary account, and loaded the sample vehicle. The dashboard showed three maintenance records and $359.99 in spending. After signing out and signing back in, the account showed the same three records and total. The first sign-in screen and the populated dashboard were captured for poster preparation. The browser used the production HTML, JavaScript, and Python `AccountHandler`. HTTP requests passed to the handler in process, with real session cookies and a disposable SQLite directory. No participant data were used.

| Action | Observed response or outcome |
| --- | --- |
| Register local account | HTTP 201, signed-in workspace opens |
| Load sample data | HTTP 201, three records, $359.99 |
| Sign out | HTTP 200, sign-in form returns |
| Sign back in | HTTP 200, same saved records and total |

## Scope of the additional evidence

The [six local account regression tests](../../CarCareLog/tests/test_owner_site.py) passed in the 87-test run. They cover signed-out access, record access and mutation across two accounts, session renewal and expiration, a stale tab after an account switch, new-ledger separation, and the account-attempt limit. These checks add evidence for [SR13 Owner data isolation](https://cloud.innoslate.com/cornell/p/746/database/entity/245397) on the tested local routes. The original chapter 13/14 findings at `ef457af` describe the single-owner service. This demonstration does not establish production multi-user authorization or complete the V08 owner-isolation check across the outage sequence.

The [chapter 14 verification protocol](../verification/chapter14-protocol.md) defines separate acceptance evidence for V03 (ten first-time vehicle owners) and V07 (seven days of availability). The automated account checks contribute no participants or monitored uptime to either case.
