# ADR 012 Local receipt image input

**Decision date:** November 22, 2026. **Scope:** local, single-owner pilot.

## Context

Owners may have a photo of a service receipt without a text copy. [ADR 011](adr-011-receipt-runtime.md) selected on-device Ollama for text drafting. That decision's Qwen2.5 measurements remain the baseline for the Chapter 11–12 trade study.

## Decision

Use the Ollama tag `qwen3.5:4b` for pasted text and JPEG/PNG images. The browser submits exactly one source to `POST /api/receipt-draft`. Images are limited to 4 MiB. The adapter sends pixels as base64 in Ollama's `images` array on loopback, with a fixed output schema, temperature 0, seed 18 and thinking disabled. The tested GGUF weight digest starts with `a9d0a3e1d8c9` and the visual projector digest with `e56a899b1540`.

The browser presents the selected photo alongside the proposed fields. A text draft can be checked against the submitted text. For a photo, the runtime supplies candidate fields, and the app has no independent transcription. Each usable field therefore receives a visual-check flag. Invalid or absent fields require entry. Only the owner's confirmed form goes to SQLite. A manual entry remains available if the model is unavailable.

## Alternatives and consequences

Retaining Qwen2.5 alone would preserve the measured text path but would still require owners to transcribe photos. A separate OCR component feeding the older model would add another runtime, another failure boundary and a need for separate OCR validation. Qwen3.5 keeps the existing local service boundary and sends no vehicle history to the model. Picture decoding and inference add latency, and visual review adds work for the owner.

Use the [image evaluation script](../CarCareLog/tools/evaluate_receipt_images.py) and the [receipt boundary tests](../CarCareLog/tests/test_receipt_runtime.py) to assess this increment. The image measurements use synthetic renders. A deployment decision for photographed receipts still requires tests with natural lighting, skew, blur and representative devices.
