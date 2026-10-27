from __future__ import annotations

import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from whytrace.agent import run_agent
from whytrace.world_model.store import WorldStoreService

load_dotenv()
st.set_page_config(page_title="WhyTrace", page_icon="🔎", layout="wide")
st.title("WhyTrace")
st.caption("Explain why a retail revenue metric changed, with every claim tied to query evidence.")
sample_mode = os.getenv("SAMPLE_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
st.sidebar.success("SAMPLE_MODE · DuckDB" if sample_mode else "REAL MODE · Zetaris JDBC")
examples = ["Why did S3 revenue drop in March 2026?", "What drove the March revenue change?", "Did returns explain the March decline?"]
st.subheader("Try a sample question")
buttons = st.columns(3)
chosen = None
for col, question in zip(buttons, examples):
    if col.button(question, use_container_width=True):
        chosen = question
question = st.text_input("Ask about a retail revenue change", value=chosen or "")
if st.button("Explain change", type="primary", disabled=not question.strip()):
    with st.spinner("Gathering and verifying query evidence…"):
        st.session_state["report"] = run_agent(question.strip())

report = st.session_state.get("report")
if report:
    st.divider()
    st.subheader("Ranked drivers")
    store = WorldStoreService()
    all_claims = report["ranked_drivers"] + report["ruled_out"]
    for rank, claim in enumerate(report["ranked_drivers"], 1):
        with st.container(border=True):
            st.markdown(f"### {rank}. {claim['title']}")
            st.write(claim["claim"])
            st.caption(f"Confidence {claim['confidence']:.0%} · Model used: {claim['model']}")
            st.success("Verified" if claim["verified"] else "Mismatch detected")
            if st.button("Why do you believe this?", key=f"why-{rank}"):
                st.session_state["provenance"] = claim["evidence_ids"]
            for eid in claim["evidence_ids"]:
                ev = store.get(eid)
                if ev:
                    with st.expander(f"Evidence {eid} · {ev['row_count']} rows"):
                        st.code(ev["sql"], language="sql")
                        st.json(ev["rows"])
    if report["ruled_out"]:
        st.subheader("Ruled out / lower priority")
        for i, claim in enumerate(report["ruled_out"]):
            with st.expander(f"{claim['title']} · {'Verified' if claim['verified'] else 'Mismatch'} · Model: {claim['model']}"):
                st.write(claim["claim"])
                for eid in claim["evidence_ids"]:
                    ev = store.get(eid)
                    if ev:
                        st.code(ev["sql"], language="sql")
                        st.json(ev["rows"])
                if st.button("Why do you believe this?", key=f"why-ruled-{i}"):
                    st.session_state["provenance"] = claim["evidence_ids"]
    if st.session_state.get("provenance"):
        st.subheader("Provenance chain")
        for ev in report["context"]["provenance"]:
            if ev["evidence_id"] in st.session_state["provenance"]:
                st.markdown(f"Claim → `{ev['evidence_id']}` → **{ev['source']}** → model `{ev['model']}`")
                st.code(ev["sql"], language="sql")
    with st.expander("Model steps"):
        st.write(f"Plan · Model used: {report['model_plan']}")
        for step in report["hypotheses"]:
            st.write(f"{step['name']} · Model used: {step['model']} · {len(step['rows'])} rows")
