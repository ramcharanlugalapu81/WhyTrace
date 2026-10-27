# WhyTrace

WhyTrace investigates why a retail revenue metric changed and ties every reported number to the SQL and returned rows that support it. The UI shows ranked drivers, ruled-out checks, model tags, verification status, and a claim-to-query provenance chain.

## Architecture

`app.py` is the Streamlit interface. `whytrace/agent.py` plans checks, generates SQL, runs queries through `zetaris_client.py`, ingests results, and builds a sourced report. `whytrace/verifier.py` re-runs cited SQL and checks each cited numeric value with a 0.5% tolerance. `whytrace/world_model/` is the minimal Meterless World Model engine: an atomic JSONL evidence store, idempotent ingest pipeline, and provenance/context builder. Evidence IDs are deterministic hashes of SQL and parameters. Request, ingest, and step logs are JSONL files under `logs/`.

The deterministic sample dataset is built in memory by `whytrace/sample_data.py`. It uses TPC-DS-style tables and plants one event: S3's daily net sales are halved in March 2026, producing an approximately 44% month-total decline from February. Electronics returns spike during March as a decoy; the return amount remains small beside the lost S3 revenue.

## Setup

Use Python 3.11 from a clean clone:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Run the app with `streamlit run app.py`. By default, `SAMPLE_MODE=true` uses the deterministic local DuckDB dataset and the offline templated model path. You can also use the three sample questions in the app.

Run tests with `pytest tests/test_world_model.py` (or `pytest` for the full suite).

## Zetaris and Meterless Nightshift

To run against a real environment, set `SAMPLE_MODE=false`, then configure `ZETARIS_JDBC_URL`, `ZETARIS_USERNAME`, `ZETARIS_PASSWORD`, and `ZETARIS_JDBC_JAR` in `.env`. Install the optional JDBC bridge with `pip install -r requirements-zetaris.txt`; a working Java runtime, Zetaris JDBC driver, network access, credentials, and compatible source schema are also required. Queries are restricted to a single read-only `SELECT` or `WITH` statement.

Configure `METERLESS_BASE_URL`, `METERLESS_RUNTIME_TOKEN`, `FAST_MODEL`, and `DEEP_MODEL` for the OpenAI-compatible Meterless Nightshift endpoint. Fast generation supplies query SQL; deep generation supplies the initial hypothesis plan. Sample mode or a missing token selects deterministic offline templates. A configured endpoint/model/schema must support the prompts and table/column names used by WhyTrace for real model-driven runs; this starter's report interpretation is tailored to the supplied retail question and sample signal. This repository does not validate an external Zetaris or Nightshift account.

## Samples and logs

`samples/question_1.json` through `question_3.json` contain the sample inputs. Matching `report_1.json` through `report_3.json` contain generated, evidence-backed outputs.

Model request metadata (timestamp, role, model, success) is in `logs/requests.jsonl`; pipeline steps are in `logs/trace.jsonl`; ingest events are in `logs/ingest.jsonl`; and persisted evidence is in `logs/evidence.jsonl`. The log directory can be redirected with `WHYTRACE_LOG_DIR`.
