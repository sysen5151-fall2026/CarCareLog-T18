"""Take an extra snapshot or repair damaged local CarCareLog storage while the site is stopped."""
import argparse
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.recovery import RecoveryError, RecoveryManager, service_lock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("backup", "recover", "list"))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ledger", type=Path, help="single-owner database file")
    source.add_argument("--accounts", type=Path, help="account-mode directory containing accounts.sqlite3")
    args = parser.parse_args()
    manager = RecoveryManager.for_ledger(args.ledger) if args.ledger else RecoveryManager.for_accounts(args.accounts)
    try:
        with service_lock(manager.archive):
            if args.action == "list":
                generations = manager.generations()
                print("\n".join(str(path) for path in generations) if generations else "No published snapshots.")
            elif args.action == "backup":
                print("Verified snapshot:", manager.snapshot())
            else:
                if not manager.database.exists() and not manager.generations():
                    raise RecoveryError("No database or published snapshot at this location.")
                manager.recover()
                print("Database integrity checked. Any missing or damaged databases were restored.")
    except (RecoveryError, sqlite3.Error, OSError) as err:
        parser.exit(1, f"CarCareLog recovery: {err}\n")


if __name__ == "__main__":
    main()
