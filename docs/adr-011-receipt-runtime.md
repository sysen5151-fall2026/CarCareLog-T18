# ADR 011 Receipt Text Runtime

**Status:** Selected for the opt-in pilot on the Chapter 11–12 branch. The provider acceptance benchmark and remote merge remain open.

The decision concerns where the receipt-text model executes for UC.1 and F.2.2.2. Both options produce an unconfirmed draft for review and leave the C.3 write boundary behind explicit owner confirmation. [Native alternatives](https://cloud.innoslate.com/cornell/p/746/diagrams/asset/318544).

Use an on-device adapter (SA.A). Its application connection is loopback only. Start an Ollama service in local-only mode and select an already installed local model with `CARCARE_OLLAMA_MODEL`. Leave that variable unset for the normal manual demo. Provisioning and pinned-model selection for a release remain open. Use `POST /internal/v1/coordinate-ai` with `vehicle_id`, `kind: receipt`, and `receipt_text`. This pilot does not receive an image or perform OCR. A successful result requires review and does not itself write a record.

The comparison used off-host request destinations, one-year incremental cost, and manual continuity during model failure. The report identifies engineering assumptions and presents weighting sensitivity. SA.A wins at the baseline privacy weight. SA.B can win when the privacy weight is lowered and the same cost and continuity assumptions are retained. The local HTTP fixture proves transport behavior and timeout recovery. Neither provider was tested for field accuracy or inference latency.

SA.B would require a vendor configuration, credentials, network policy, a policy-approved input subset, a retention review, and a throughput and outage benchmark. Its draft validation and confirmation controls would remain the same. Deployment also requires comparing both candidates using the same labeled receipts before making field-accuracy claims.

Sources: [Ollama generate contract](https://docs.ollama.com/api/generate), [Ollama local-mode configuration](https://docs.ollama.com/faq), [hosted pricing reference](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
