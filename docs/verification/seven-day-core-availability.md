# V07 core service availability

The [frozen V07 protocol](chapter14-protocol.md) calls for at least 99% core access over seven consecutive days. At one dashboard read per minute, the window contains **10,080** scheduled minutes and requires **9,980** successful reads. Availability here describes the single-owner local pilot on the chosen computer. The account-mode health route, model inference speed and owner task times measure different behaviors.

## Run on the designated new Windows PC

Download the team's release containing `run_availability_pilot.py`, extract the whole archive to a permanent folder and open PowerShell in the folder containing that script. Use Python 3.10 or later. The pilot uses Python's standard library. The model, a cloud API key and receipt photos are unnecessary for this dashboard measurement. Keep the same extracted code and PC throughout the seven-day window.

```powershell
py -3 --version
py -3 run_availability_pilot.py check
py -3 run_availability_pilot.py run
```

`check` makes one real read in temporary storage, closes its own test service and leaves no official observations. Run `run` **once on the designated PC when ready to start the clock**. It creates a private synthetic fixture in `$HOME\CarCareLog-V07-Pilot`, binds only to 127.0.0.1, confirms the dashboard works, records the build fingerprint and starts the minute collector. The output gives UTC start and end times. Keep that PowerShell window open, keep the computer plugged in and choose a power setting that keeps it awake while plugged in. The display may turn off. For a laptop, keep the lid open unless its power settings keep it awake when closed. If port 8017 is already in use, choose a free port with e.g. `--port 18117` for both commands before the official run.

After a reboot or closed terminal, open the same release directory and rerun `py -3 run_availability_pilot.py run`. A process lock avoids duplicate launches. The collector resumes the same window and port. If the fixture process exits during collection, read failures count; stop and resume the wrapper to restart the fixture. The pilot clock includes outages, sleep and missed minutes. The helper does not install a startup service or change the PC's settings.

In a separate PowerShell window in the same release folder:

```powershell
py -3 run_availability_pilot.py status
py -3 run_availability_pilot.py export --output "$HOME\Desktop\T18-V07-results.zip"
```

Export to a new filename each time. The ZIP contains a consistent SQLite copy of the raw observations, the build and computer identity, and the counts and verdict at export time. The final status is available once all 10,080 minutes have elapsed. Use the final ZIP to update the report and retain the raw evidence on the designated PC.

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
