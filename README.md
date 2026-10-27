# WhyTrace

WhyTrace investigates why a retail revenue metric changed and ties every reported number to the SQL and returned rows that support it. The UI shows ranked drivers, ruled-out checks, model tags, verification status, and a claim-to-query provenance chain.

## Hackathon problem and track

**Problem statement:** Retail operators can see that revenue fell, but finding why means manually stitching together store sales, returns, product mix, and inventory data. That investigation is slow, fragmented, and hard to audit. **How might we coordinate specialized agents to investigate a retail KPI change and return an explanation whose every number can be traced back to a query and independently rechecked?**

**Target users:** Retail operations, finance, and merchandising analysts who need to explain revenue movement and decide what to investigate next.

**Selected track:** *The Agent That Can Explain Why.* WhyTrace uses separate planning, SQL investigation, adversarial review, and explanation roles. A deterministic verifier re-runs each cited query and checks its numeric claims before the report is shown.

**Short description:** WhyTrace is a multi-agent retail analyst that turns the question "why did revenue change?" into a ranked, query-backed investigation instead of an untraceable AI answer.

## Architecture

`app.py` is the Streamlit interface. `whytrace/agent.py` coordinates four roles: Meterless Nightshift plans hypotheses, writes SQL, and explains results; Zetaris executes the SQL in real mode (or DuckDB in sample mode); NVIDIA Nemotron independently challenges the evidence; and the deterministic verifier re-runs cited SQL and checks each numeric value with a 0.5% tolerance. `whytrace/world_model/` is the minimal Meterless World Model engine: an atomic JSONL evidence store, idempotent ingest pipeline, and provenance/context builder. Evidence IDs are deterministic hashes of SQL and parameters. Request, ingest, and step logs are JSONL files under `logs/`.

The deterministic sample dataset is built in memory by `whytrace/sample_data.py`. It uses TPC-DS-style tables and plants one event: S3's daily net sales are halved in March 2026, producing an approximately 44% month-total decline from February. Electronics returns spike during March as a decoy; the return amount remains small beside the lost S3 revenue.

## Setup

Use Python 3.11 from a clean clone:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Run the app with `streamlit run app.py`. By default, `SAMPLE_MODE=true` uses the deterministic local DuckDB dataset. If `METERLESS_RUNTIME_TOKEN` is configured, the agent uses Nightshift for hypothesis planning, SQL generation, and its evidence-grounded explanation while keeping data local. Without a token, it clearly labels and uses the deterministic offline evidence agent. You can try the three sample questions in the app.

This is a retail analytics agent, not an unrestricted general-purpose chatbot. Its supported evidence is store revenue, item and category sales, returns, and average inventory from the six documented tables; month-over-month analysis requires both months to exist in the source. Ask questions in natural language within that scope, and it routes the lead analysis to the matching evidence type. The three prompt buttons are examples only; the question field is open-ended.

For a two-minute screen recording, press **Load the 2-minute demo question**, then press **Investigate with WhyTrace** to begin. Choosing an example never starts the agent by itself. The investigation stays expanded and shows planner, SQL, query execution, Nemotron review, and verification stages as they happen. Then show the ranked answer, open a SQL evidence card, and finish on the provenance chain. The sidebar includes a timed recording outline.

## Deploy a shareable demo

The app is ready for Streamlit Community Cloud in sample mode. Sign in at [share.streamlit.io](https://share.streamlit.io/) with the GitHub account that can access this repository, choose **Create app**, then select repository `ramcharanlugalapu81/WhyTrace`, branch `main`, and entrypoint `app.py`. Choose Python 3.11 in advanced settings if offered, then click **Deploy**. `SAMPLE_MODE` defaults to true, so the hosted app uses DuckDB sample data. Without a token it runs the deterministic evidence agent and labels that mode clearly. To enable live Nightshift planning, SQL generation, and explanation while keeping sample data, add these values under the app's **Settings > Secrets**:

```toml
SAMPLE_MODE = "true"
METERLESS_BASE_URL = "https://your-meterless-endpoint"
METERLESS_RUNTIME_TOKEN = "your-runtime-token"
FAST_MODEL = "your-fast-model"
DEEP_MODEL = "your-deep-model"
NVIDIA_API_KEY = "your-personal-nvidia-key"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NEMOTRON_MODEL = "nvidia/nemotron-3.5-bolt-e4b"
```

The app reads Streamlit Secrets directly. Zetaris JDBC credentials are only needed if you also set `SAMPLE_MODE = "false"`. Community Cloud must be connected to the GitHub account and the deploy button must be clicked by an account owner; cloud credentials are not stored in this repository.

Run tests with `pytest tests/test_world_model.py` (or `pytest` for the full suite).

## Zetaris and Meterless Nightshift

To run against a real environment, set `SAMPLE_MODE=false`, then configure `ZETARIS_JDBC_URL`, `ZETARIS_USERNAME`, `ZETARIS_PASSWORD`, and `ZETARIS_JDBC_JAR` in `.env`. Install the optional JDBC bridge with `pip install -r requirements-zetaris.txt`; a working Java runtime, Zetaris JDBC driver, network access, credentials, and compatible source schema are also required. Queries are restricted to a single read-only `SELECT` or `WITH` statement.

Configure `METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN`, `FAST_MODEL`, and `DEEP_MODEL` for the OpenAI-compatible Meterless Nightshift endpoint. Fast generation writes SQL; deep generation plans investigations and produces a grounded explanation from query results.

NVIDIA Nemotron is the independent skeptic. Create your own NVIDIA API key from the [Nemotron 3.5 Bolt model page](https://build.nvidia.com/nvidia/nemotron-3_5-bolt-e4b), then set `NVIDIA_API_KEY`. NVIDIA currently marks this as a free endpoint for development; access is tied to your NVIDIA account and the hosted API has its own trial terms and availability. **There is deliberately no shared API key in this repository.** For Streamlit Community Cloud, put the key in **Settings > Secrets**, never in GitHub. The default uses `https://integrate.api.nvidia.com/v1` and `nvidia/nemotron-3.5-bolt-e4b`; override with `NVIDIA_BASE_URL`, `NEMOTRON_MODEL`, or `NEMOTRON_REVIEW_MODEL` if needed.

With both providers configured, the app uses Nightshift for planning/SQL/explanation and Nemotron for an independent evidence review. With only a Nemotron key, it routes the roles through Nemotron. With no keys or an API failure, it falls back to a clearly labelled deterministic evidence agent. The report ranking and cited numbers always come from query results, never model-generated measurements. This repository does not include or validate external Zetaris, Nightshift, or NVIDIA credentials.

**Sponsor integration status:** The Zetaris JDBC adapter and Meterless Nightshift/World Model interfaces are implemented and configurable; an external Zetaris or Nightshift account was not available for live testing. NVIDIA NIM is integrated through its OpenAI-compatible chat endpoint and can be exercised as soon as you add your personal API key.

**Pre-existing work disclosure:** The initial WhyTrace prototype, synthetic retail data, DuckDB adapter, JSONL evidence store, and basic Streamlit flow were built before this multi-agent submission revision. The new contribution is the coordinated specialist-agent flow, NVIDIA Nemotron skeptic integration, grounded explanation stage, model routing/secrets support, refreshed premium UI, and expanded verification coverage. Declare the prototype components as pre-existing in the submission form.

## Samples and logs

`samples/question_1.json` through `question_3.json` contain the sample inputs. Matching `report_1.json` through `report_3.json` contain generated, evidence-backed outputs.

Model request metadata (timestamp, role, model, success) is in `logs/requests.jsonl`; pipeline steps are in `logs/trace.jsonl`; ingest events are in `logs/ingest.jsonl`; and persisted evidence is in `logs/evidence.jsonl`. The log directory can be redirected with `WHYTRACE_LOG_DIR`.
