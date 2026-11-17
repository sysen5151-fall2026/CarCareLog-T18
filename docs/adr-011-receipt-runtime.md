# ADR 011 Receipt Text Runtime

**Status:** Selected for the opt-in pilot and merged to `main`. A pinned real local model and the provider acceptance benchmark remain open.

The decision concerns where the receipt-text model executes for UC.1 and F.2.2.2. Both options produce an unconfirmed draft for review and leave the C.3 write boundary behind explicit owner confirmation. [Native alternatives](https://cloud.innoslate.com/cornell/p/746/diagrams/asset/318544).

Use an on-device adapter (SA.A). Its application connection is loopback only. Start an Ollama service in local-only mode and select an already installed local model with `CARCARE_OLLAMA_MODEL`. Leave that variable unset for the normal manual demo. Provisioning and pinned-model selection for a release remain open. Use `POST /internal/v1/coordinate-ai` with `vehicle_id`, `kind: receipt`, and `receipt_text`. This pilot does not receive an image or perform OCR. A successful result requires review and does not itself write a record.

The comparison used off-host request destinations, one-year incremental cost, and manual continuity during model failure. SA.B uses GPT-6.1 Sol as the hosted comparator. SA.A wins both baseline weight settings. Fifteen additional minutes of local setup put SA.A over the illustrative USD 80 budget. SA.B is then affordable if off-host processing is approved. The local HTTP fixture proves transport behavior and timeout recovery. Neither provider was tested for field accuracy or inference latency.

SA.B would require a vendor configuration, credentials, network policy, a policy-approved input subset, a retention review, and a throughput and outage benchmark. Its draft validation and confirmation controls would remain the same. Deployment also requires comparing both candidates using the same labeled receipts before making field-accuracy claims.

Sources: [Ollama generate contract](https://docs.ollama.com/api/generate), [Ollama local-mode configuration](https://docs.ollama.com/faq), [hosted GPT-6.1 Sol pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol).
