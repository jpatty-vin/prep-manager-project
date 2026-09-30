# 📦 AI Visual Prep Compliance Agent

An automated visual inspection and decision-traceability system for e-commerce fulfillment centers (e.g., Amazon FBA prep compliance). This system evaluates package photographs against strict prep guidelines, logs verifiable audit trails (CUBE Evidence Record Contract), supports manual operator overrides, and evaluates performance against human labeler benchmarks.

---

## 🌟 Key Features

1. **Multi-Model Vision Fallback Engine**: Iterates through Gemini models to ensure high availability during inspection.
2. **CUBE Evidence Record Contract Compliance**: Generates standardized, audit-ready JSON evidence records with SHA-256 image checksums, content integrity hashes, latency, and full inspection details.
3. **Uncertainty Guardrails**: Explicitly outputs `UNCERTAIN` for blurry, cropped, or ambiguous images to prevent false passes/fails.
4. **Operator Overrides & Decision Traceability**: Streamlit dashboard UI allowing operators to submit human corrections with justification logs, automatically updating record status to `OVERRIDDEN`.
5. **Evaluation Harness**: Script to compute Cohen's Kappa inter-rater agreement, false positive/negative rates, latency, and uncertainty metrics.

---

## 🚀 Quickstart

### 1. Prerequisites & Environment Setup

Ensure Python 3.10+ is installed. Install required packages:

```bash
pip install google-genai streamlit python-dotenv pillow scikit-learn numpy pydantic