# V07 core service availability

The [frozen V07 protocol](chapter14-protocol.md) calls for at least 99% core access over seven consecutive days. At one dashboard read per minute, the window contains **10,080** scheduled minutes and requires **9,980** successful reads. Availability here describes the single-owner local pilot on the chosen computer. The account-mode health route, model inference speed and owner task times measure different behaviors.

## Prepare the pilot

1. In a terminal at the repository root, start a dedicated fixture with `python run_demo.py --port 8017 --data-dir "../v07-fixture"`. The example stores its records next to the checkout. On macOS or Linux use `python3` for the commands below and for the app.
2. Open `http://127.0.0.1:8017` and select **Load demo data** once. In a fresh fixture its synthetic vehicle has ID 1 and contains three sample records. Keep the pilot separate from real owner data and leave the fixture intact.
3. In a second terminal, run the readiness check.

```shell
python CarCareLog/tools/availability_study.py check --port 8017 --vehicle-id 1
```

The check makes one read through the actual HTTP handler, SQLite ledger and dashboard calculation. It requires HTTP 200, the requested vehicle, at least one record associated with it, and a total matching its records. The one-shot check creates no observation file and supplies no seven-day result.

## Collect a real seven-day window

When the team is ready to begin, choose a new evidence path in an existing local folder **outside the repository**. For example, from the repository root use the parent directory.

```shell
python CarCareLog/tools/availability_study.py monitor ../v07-pilot.sqlite3 --port 8017 --vehicle-id 1
```

Keep the pilot computer awake, application available and collector terminal open. The collector runs in the foreground and automatically ends after seven consecutive 24-hour periods. Its first launch records the UTC start, target port and vehicle. Ctrl+C stops collection. Resume the original window and fixture with `python CarCareLog/tools/availability_study.py monitor ../v07-pilot.sqlite3`. The clock continues during shutdown and sleep. A duplicate launch cannot record a second result for the same minute. Collection issues one read per real minute with a five-second timeout, shortened near the end of a slot. It never replays missed minutes.

From another terminal, view progress with:

```shell
python CarCareLog/tools/availability_study.py status ../v07-pilot.sqlite3
```

The summary gives the UTC window, completed minute count, successful reads, failed reads, and missing or interrupted reads. The current minute is included when it ends. Unobserved minutes count against availability. If a team can independently document an instrumentation failure, retain the raw data and state the reason and effect separately. The collector makes no automatic exclusions. Status stays **pending** until the seven days have elapsed. The completed status is **pass** at 9,980 or more successful minutes, otherwise **fail**. Cite the build revision, computer and raw counts when reporting a result. The evidence database contains sample times, response classifications and timings, with no receipt contents, account credentials or vehicle names.
