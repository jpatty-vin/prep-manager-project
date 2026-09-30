### File 2: `ARCHITECTURE.md`

Create or replace **`ARCHITECTURE.md`** with the following content:

```markdown
# 🏗️ System Architecture & Design Specification

## Overview

The **AI Visual Prep Compliance Agent** is designed for high-throughput fulfillment center environments where prep accuracy, auditability, and speed are critical.
[ Packaging Photos / Webcam ]
│
▼
[ Streamlit UI / CLI ]
│
▼
[ Multi-Model Fallback ] ───► (Gemini 2.5 Flash / 1.5 Flash / 1.5 Pro)
│
▼
[ CUBE Evidence Generator ]
│
├─► SHA-256 Image Hashes
├─► Inspection Check Mapping
└─► Payload SHA-256 Content Hash
│
▼
[ Operator Override Handler ] ───► Appends override entries & recalculates outcome
## Key Components

### 1. Ingestion & Preprocessing
* **Multi-Image Support**: Accepts multiple image angles (e.g., polybag seal, barcode, warning label).
* **SHA-256 Hashing**: Computes individual SHA-256 hashes per input image to guarantee cryptographic traceability.

### 2. Multi-Model Vision Fallback Strategy
* Executes requests against primary and fallback models (e.g., `gemini-2.5-flash`, `gemini-1.5-flash`, `gemini-1.5-pro`) to handle rate limits (`429`) or temporary service unavailability (`503`).
* Logs the winning `model_version` and exact execution time (`latency_ms`) directly into the evidence payload.

### 3. Uncertainty Guardrails
* Mandatory instruction rules force the model to issue `UNCERTAIN` when visual evidence is missing, obscured, or ambiguous.
* Prevents hallucinated passes/fails on unverified prep standards.

### 4. CUBE Evidence Record Contract
Every run produces an audit-compliant JSON record adhering to:
* **Identification**: `record_id`, `schema_version` (`1.0.0`), `organization_id`, `client_id`, `agent`, `operator_label`.
* **Verification Data**: `images` (with SHA-256 checksums), `checks` (verdict, confidence, detail), `outcome` (`PASS` | `FAIL` | `UNCERTAIN`).
* **Audit Trail**: `overrides[]` list and overall `status` (`AUTOMATED` vs `OVERRIDDEN`).
* **Integrity**: `content_hash` derived from hashing the canonical JSON representation of the record.

### 5. Human-in-the-Loop Operator Overrides
* Warehouse operators can manually correct false positives or negatives through the Streamlit interface.
* Each override logs `check_key`, `original_verdict`, `overridden_verdict`, `reason`, and `timestamp`.
* Modifying any check automatically updates the overall package outcome and sets `status = "OVERRIDDEN"`.

---

## Evaluation Methodology

The benchmarking harness (`evaluate.py`) measures:
1. **Human Inter-Rater Agreement**: Uses **Cohen's Kappa ($\kappa$)** to establish ground-truth reliability between human labelers.
2. **System Latency**: Measures end-to-end execution latency per package in milliseconds.
3. **Uncertainty Rate**: Tracks proportion of cases safely flagged as `UNCERTAIN` for human review.