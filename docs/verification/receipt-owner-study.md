# Camera receipts and first-time owner study

The product team can run two checks with the production web form, reviewed receipt fields and real local Ollama model. The camera benchmark measures extraction. The owner study measures whether a first-time user can independently save an accurate record within 180 seconds, as defined in [V03](chapter14-protocol.md). The archived [20 clean synthetic images](../evidence/chapter14-qwen35-receipt-images.md) provide a separate baseline.

## Prepare photographs and answer keys

From the repository root, start Ollama with `qwen3.5:4b` installed. Create a private working folder outside the repository and team Drive. In PowerShell run

```powershell
$studyFolder = Join-Path $env:USERPROFILE 'CarCareLog-owner-study'
python CarCareLog/tools/receipt_owner_study.py init "$studyFolder"
```

Place at least two distinct, de-identified, permitted camera photos of vehicle-service receipts in the folder. Use JPEG or PNG, up to 4 MiB each. Remove names, addresses, phone numbers, license plates, VINs and payment details before collection. Preserve the six fields used for scoring. Include a range of lighting and angles such as glare, faded print, skew, and a subtotal close to the amount paid. For the timed study choose comparably difficult single-service receipts with readable date, shop, final USD total, odometer and unit. Keep the number of photos and their order fixed across the ten participants.

Edit `cases.json` in the folder. For each photo, give a short case ID, local filename and photographic condition. A second reader should check the answer key directly against the photo. The six labels are `service_date` (YYYY-MM-DD), `service_item` (a supported service), `category` (Maintenance or Repair), `mileage` (whole km), `cost` (total paid in USD with two decimal places) and `provider` (business name). For miles multiply by 1.609344 and round to the nearest whole km. Keep this file and its photos out of view of participants until their assigned task starts. Share only aggregate results.

## Measure photo extraction

```powershell
python CarCareLog/tools/receipt_owner_study.py photos "$studyFolder"
```

The application sends each photo to the local model. The tool reports elapsed model-and-review time and which fields differ from the independently checked label. An unavailable model earns zero of six fields for that photo. Record sample count, number of correct fields out of all attempted fields, conditions that produced errors and model tag. These timings exclude user interactions.

## Observe ten first-time vehicle owners

Enroll ten people who maintain a vehicle and have never used CarCareLog. Assign P01 through P10 without recording names. For each participant run, for example

```powershell
python CarCareLog/tools/receipt_owner_study.py trial "$studyFolder" P01
```

1. The tool opens the normal application at a temporary local address with a fresh, single study vehicle. Only the AI-assisted task has the local receipt assistant enabled. Ensure Ollama is available in advance. Use the same device and setup across participants.
2. Explain the task in one sentence: “Record the service on the assigned receipt for this vehicle and tell me when you see the saved record.” Ask them to use the photo-drafting option in the first task. Show the dashboard without demonstrating the controls. Press Enter at the prompt when the participant is ready, then reveal the assigned photo immediately. Supply the filename and folder on screen. For manual entry, open the assigned photo for reference at the same start cue.
3. Let the participant find the entry form, read the image, check every proposed value and complete the save. Press Enter **when the participant sees the saved record** or gives up. The visible completion time includes file selection, inference, corrections, confirmation and dashboard feedback. Record any coaching when prompted. Keep unsuccessful attempts. The tool also timestamps the server save, checks the vehicle, row count and six persisted values, and counts differences between the draft and saved fields. A manual fallback after a failed draft remains an observed attempt and earns no AI-assisted pass.
4. Run the paired manual task after the AI task. Each participant receives a different receipt for manual entry. Case assignments rotate across participants so both cases appear in each mode. AI always comes first to preserve V03's first-time condition. Manual second-task familiarity may affect the paired comparison.
5. Repeat for the next ID. An interrupted run can resume at the manual task if an AI observation already exists. To record an abandonment during a live trial, press Enter and finish the observation. Each completed trial writes only a pseudonymous local observation with timings, field names and outcomes. The study database is discarded after the task.

## Interpret the results

```powershell
python CarCareLog/tools/receipt_owner_study.py summary "$studyFolder"
```

The tool leaves V03 pending until it has all ten distinct AI observations. At least nine must accurately save the assigned photographed receipt without help within 180 seconds. It also reports which draft fields owners changed and the median of each complete, accurate, unaided pair's **manual seconds minus AI seconds**. A positive difference favors AI for those pairs. Report the eligible pair count and the separate failure count alongside that median. Only publish an observed V03 outcome after collecting the owner sessions.
