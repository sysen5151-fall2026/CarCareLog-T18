# Local storage recovery

Both classroom launch modes check database integrity before serving requests. A missing or damaged database triggers restoration from the newest matching snapshot that passes its SHA-256, SQLite structure, application table and foreign-key checks. A healthy ledger stays in place. An unreadable directory, locked storage or an unrelated database schema stops startup for operator review. If every candidate is unusable, the service reports the failure and preserves the original.

## Automatic snapshots

The service takes a snapshot at startup, once per hour while running, and on an orderly shutdown. It retains the newest 24 complete generations. SQLite's online backup API copies committed data while owners can continue working. A generation is published after its databases pass validation. An interrupted backup leaves the previous generation available. A forced termination can omit the shutdown snapshot.

Single-owner snapshots live in a sibling directory named `.carcare-recovery-ledger-<database filename>`. In account mode they live in `accounts/.carcare-recovery-accounts` under the classroom data directory. A registry snapshot contains the password hashes and its registered owners' separate ledgers. Active sessions are removed from the copy. A restored registry requires a fresh login. Registry and ledger snapshots are captured sequentially, so each ledger represents its own capture time.

Snapshots contain private records and should stay in the owner's protected data directory. The default snapshots share the active disk. Disk loss requires a separately retained copy of a completed snapshot generation and its checksums. Before recovery, stop any external SQLite editors or old application versions accessing these files.

## Operator commands

From the repository root, with the app stopped, select the actual data path used by the launcher. In these examples `classroom` is the directory previously supplied to `run_demo.py --data-dir`.

```sh
python CarCareLog/tools/recover_storage.py list --ledger classroom/single-owner.sqlite3
python CarCareLog/tools/recover_storage.py backup --ledger classroom/single-owner.sqlite3
python CarCareLog/tools/recover_storage.py recover --accounts classroom/accounts
```

Each action accepts either `--ledger` or `--accounts`. The operator and service share one exclusive process lock. Recovery preserves copies of damaged files beneath `damaged-*` in the snapshot directory. Inspect them before any manual disposal. For a recovered account registry, accounts created after the recovery point may need operator reconciliation with surviving ledger files. The next startup logs a warning if the selected snapshot exceeds 24 hours. A recent valid snapshot limits the possible loss to changes after its capture.

## Controlled exercise

Run `python CarCareLog/tools/measure_recovery.py` from the repository root. The drill creates disposable storage, seeds three synthetic receipts, captures a verified snapshot, adds one extra vehicle and damages the saved ledger. The account scenario also removes the synthetic account registry. The normal `run_demo.py` entry point starts on loopback. Successful recovery requires HTTP access to all three receipts and their $359.99 total. The account scenario also requires fresh logins and an empty second-owner ledger.

| Measured in the November 23, 2026 local exercise | Single owner | Two local accounts |
| --- | ---: | ---: |
| Backup-point age at the fault, conservative upper bound | 0.0277 s | 0.0426 s |
| Fault injection to validated dashboard response | 0.5628 s | 0.7977 s |
| Receipts and total recovered | 3 / $359.99 | 3 / $359.99 |

Both exercises used a recent same-disk snapshot and met the 24-hour recovery-point target for those two faults. The newer vehicle was absent after each restore, demonstrating the rollback boundary. The automated tests also exercise the periodic timer, concurrent uncommitted writes, fallback from a damaged snapshot, isolation after registry repair, and retention of damaged files when recovery cannot proceed. The clock for backup-point age starts at snapshot capture. The recovery-time clock starts at fault injection and stops after the dashboard check. A long shutdown, persistent backup errors, loss of all copies or hardware replacement can change both outcomes. [Machine-readable measurements](../evidence/local-recovery-drill.json).
