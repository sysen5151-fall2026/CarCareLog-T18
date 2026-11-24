# ADR 013 — Separate owner ledgers on a classroom computer

November 23, 2026. This decision applies to the downloadable, loopback-only poster demonstration.

## Context

A visitor can download CarCareLog and run it on their own computer. The original single-owner entry point uses one SQLite database. If two visitors use the same installation, they need a way to keep their demonstration records separate. The trace target is SR13, Owner data isolation.

## Decision

`run_demo.py --accounts` opens a local registration and sign-in screen. A successful login selects an account-specific SQLite ledger. Every product operation, including record confirmation, seeding, history, reminders and exports, runs against that ledger. The account database stores a salted password digest and a digest of each eight-hour session token. Signing out revokes the server-side session. The browser supplies the workspace identifier with application requests to detect a form opened under a different account.

Both entry points bind to 127.0.0.1. The account server accepts writes only from its configured local origin. The launcher puts the single-owner database and the account ledgers in separate directories under the visitor's classroom data folder. It never assigns an existing single-owner database to a new account. The same F.2.2 receipt checks, C.3 record storage logic and optional on-device Ollama adapter serve both modes. Default single-owner use remains available.

## Scope and verification

The [account tests](../CarCareLog/tests/test_owner_site.py) run two accounts through actual local HTTP handlers. Identical numeric vehicle IDs in separate ledgers return separate histories. Tests exercise signed-out reads and writes, wrong-origin requests, a stale browser workspace, session expiry and revocation, new accounts, and attempt limits. These are application-level checks on one computer. Files remain accessible to its operating-system owner. Public hosting, cross-device accounts, password recovery and protection from someone with filesystem access are outside this classroom design.

Results from these automated tests do not add observations to V03. Its acceptance condition still calls for at least nine of ten first-time vehicle owners to save an accurate record without assistance within 180 seconds. See the [owner study protocol](verification/receipt-owner-study.md).
