from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Community Cloud stores deployment values in st.secrets rather than process env.
for _key in ("SAMPLE_MODE", "METERLESS_BASE_URL", "METERLESS_RUNTIME_TOKEN", "FAST_MODEL", "DEEP_MODEL",
             "NVIDIA_API_KEY", "NVIDIA_BASE_URL", "NEMOTRON_MODEL", "NEMOTRON_FAST_MODEL", "NEMOTRON_REVIEW_MODEL",
             "ZETARIS_JDBC_URL", "ZETARIS_USERNAME", "ZETARIS_PASSWORD", "ZETARIS_JDBC_JAR"):
    if not os.getenv(_key):
        try:
            if _key in st.secrets:
                os.environ[_key] = str(st.secrets[_key])
        except Exception:
            pass

from whytrace.agent import run_agent
from whytrace.llm import _setting
from whytrace.world_model.store import WorldStoreService


st.set_page_config(page_title="WhyTrace | Revenue intelligence", page_icon="W", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=Manrope:wght@400;500;600;700;800&display=swap');
:root { --vanilla:#FFEBAF; --moonstone:#4C9DB0; --ink:#17333a; --muted:#61757a; --paper:#fffdf5; --line:#e8dfc3; --deep:#173d45; }
html, body, [class*="css"] { font-family:'Manrope',sans-serif; color:var(--ink); }
.stApp { background:linear-gradient(180deg,#fff9e8 0%,#fffdf6 54%,#fff9e8 100%); }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stSidebar"] { background:#4C9DB0; border-right:1px solid rgba(23,51,58,.12); }
[data-testid="stSidebar"] * { color:#fffdf5; }
[data-testid="stSidebar"] [data-testid="stMetricValue"] { color:var(--vanilla); }
section.main > div { max-width:1320px; padding-top:2.1rem; }
.brandmark { font-size:.73rem; font-weight:800; letter-spacing:.2em; text-transform:uppercase; color:#438b9b; margin-bottom:1rem; }
.hero { position:relative; overflow:hidden; background:var(--vanilla); border:1px solid #eadb9f; border-radius:24px; padding:2.1rem 2.4rem; margin:0 0 1.5rem 0; box-shadow:0 12px 32px rgba(89,91,52,.06); }
.hero::after { content:''; position:absolute; right:7%; top:12%; width:150px; height:150px; border:1px solid rgba(76,157,176,.25); border-radius:50%; box-shadow:0 0 0 18px rgba(76,157,176,.05),0 0 0 38px rgba(76,157,176,.035); animation:orbitPulse 5s ease-in-out infinite; }
.hero h1 { font-family:'DM Serif Display',Georgia,serif; font-size:clamp(2.6rem,5vw,4.3rem); line-height:.99; letter-spacing:-.035em; color:#173d45; margin:0 0 .65rem 0; }
.hero h1 em { color:#4C9DB0; font-style:italic; }
.hero p { max-width:680px; font-size:1rem; line-height:1.65; color:#526b6d; margin:0; }
.eyebrow { font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; color:#54858b; font-weight:800; margin-bottom:.75rem; }
.panel { background:var(--paper); border:1px solid var(--line); border-radius:18px; padding:1.35rem 1.5rem; }
.section-title { font-family:'DM Serif Display',Georgia,serif; font-size:1.8rem; color:var(--deep); margin:.2rem 0 .3rem 0; }
.subtle { color:var(--muted); font-size:.9rem; }
.stButton > button { border-radius:12px; border:1px solid #c6dce0; background:#f4fbfb; color:#285d67; font-weight:700; min-height:2.8rem; transition:all .18s ease; }
.stButton > button:hover { border-color:var(--moonstone); color:#173d45; background:#e7f4f5; transform:translateY(-2px); box-shadow:0 9px 22px rgba(76,157,176,.16); }
.stButton > button[kind="primary"] { background:#4C9DB0; color:white; border-color:#4C9DB0; box-shadow:0 8px 18px rgba(76,157,176,.18); }
.stButton > button[kind="primary"]:hover { background:#347f90; color:white; }
.stTextInput input { border-radius:12px; background:#fffefa; border:1px solid #d9ddcb; min-height:3rem; }
[data-testid="stMetric"] { background:#fffdf5; border:1px solid #e8dfc3; border-radius:15px; padding:1rem 1.1rem; }
[data-testid="stMetricLabel"] { color:#65777a; font-weight:700; }
[data-testid="stMetricValue"] { color:#173d45; font-family:'DM Serif Display',Georgia,serif; }
[data-testid="stExpander"] { background:#fffdf8; border:1px solid #e7e0cd; border-radius:14px; }
.status { display:inline-block; padding:.33rem .65rem; border-radius:999px; font-size:.72rem; letter-spacing:.04em; text-transform:uppercase; font-weight:800; background:#e3f1e8; color:#326c51; }
.status.ai { background:#dceff2; color:#246676; }
.status.offline { background:#fff0cf; color:#8b6422; }
.status::before { content:''; display:inline-block; width:7px; height:7px; margin-right:.42rem; border-radius:50%; background:currentColor; vertical-align:1px; }
.status.ai::before { animation:statusPulse 1.5s ease-in-out infinite; }
.process-rail { display:flex; align-items:center; justify-content:space-between; gap:.7rem; padding:.9rem 1.2rem; margin:.9rem 0 1.15rem; background:#fffdf5; border:1px solid var(--line); border-radius:16px; color:#386d77; font-size:.78rem; font-weight:800; letter-spacing:.035em; }
.process-step { animation:revealUp .5s ease-out both; }
.process-step:nth-child(3) { animation-delay:.12s; }.process-step:nth-child(5) { animation-delay:.24s; }.process-step:nth-child(7) { animation-delay:.36s; }
.process-arrow { color:#9abcc0; animation:arrowGlow 1.8s ease-in-out infinite; }
.claim { font-size:1.08rem; line-height:1.65; color:#28484c; }
.stSuccess, .stAlert { border-radius:12px; }
hr { border-color:#e8dfc3; }
footer { visibility:hidden; }
@keyframes revealUp { from { opacity:0; transform:translateY(12px); } to { opacity:1; transform:translateY(0); } }
.brandmark { animation:revealUp .42s ease-out both; }
.hero { animation:revealUp .56s cubic-bezier(.2,.7,.25,1) .04s both; }
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stExpander"] { animation:revealUp .42s ease-out both; transition:box-shadow .2s ease,border-color .2s ease,transform .2s ease; }
[data-testid="stVerticalBlockBorderWrapper"]:hover { border-color:#b9d7dc; box-shadow:0 10px 24px rgba(23,61,69,.07); }
.stTextInput input:focus { border-color:var(--moonstone); box-shadow:0 0 0 3px rgba(76,157,176,.15); }
.stApp { animation:pageIn .55s ease-out both; }
@keyframes pageIn { from { opacity:.35; } to { opacity:1; } }
@keyframes softGlow { 0%,100% { box-shadow:0 0 0 rgba(76,157,176,0); } 50% { box-shadow:0 0 24px rgba(76,157,176,.18); } }
[data-testid="stStatusWidget"] { border:1px solid #b9d7dc; border-radius:16px; background:#f3fbfb; animation:softGlow 2.4s ease-in-out infinite; }
[data-testid="stStatusWidget"] svg { color:#347f90; }
[data-testid="stProgressBar"] > div > div > div > div { background:linear-gradient(90deg,#4C9DB0,#80c7ca,#4C9DB0); background-size:200% 100%; animation:shimmer 1.5s linear infinite; }
@keyframes shimmer { to { background-position:-200% 0; } }
@keyframes orbitPulse { 0%,100% { transform:scale(.96) rotate(0); opacity:.68; } 50% { transform:scale(1.04) rotate(12deg); opacity:1; } }
@keyframes statusPulse { 0%,100% { opacity:.45; box-shadow:0 0 0 0 rgba(76,157,176,.28); } 50% { opacity:1; box-shadow:0 0 0 5px rgba(76,157,176,.12); } }
@keyframes arrowGlow { 0%,100% { opacity:.45; } 50% { opacity:1; } }
[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(2) { animation-delay:.06s; }
[data-testid="stVerticalBlockBorderWrapper"]:nth-of-type(3) { animation-delay:.12s; }
.stCaption { color:#61757a; }
@media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation-duration:.01ms !important; animation-iteration-count:1 !important; scroll-behavior:auto !important; transition-duration:.01ms !important; } }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("<div style='font-family:DM Serif Display,Georgia,serif;font-size:2rem;line-height:1;color:#fffdf5'>WhyTrace</div><div style='opacity:.82;margin-top:.4rem;font-size:.82rem'>Evidence-led retail intelligence</div>", unsafe_allow_html=True)
    st.divider()
    has_token = bool(_setting("METERLESS_RUNTIME_TOKEN").strip())
    has_nvidia = bool(_setting("NVIDIA_API_KEY").strip())
    live_ai = has_token or has_nvidia
    provider_label = ("Nightshift + Nemotron configured" if has_token and has_nvidia else
                      "Nightshift configured" if has_token else "Nemotron configured" if has_nvidia else "Offline evidence agent")
    st.markdown(f"<span class='status {'ai' if live_ai else 'offline'}'>{provider_label}</span>", unsafe_allow_html=True)
    sample_mode = _setting("SAMPLE_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
    st.markdown(f"<p style='font-size:.82rem;margin-top:.7rem;opacity:.88'>Data source · {'Sample DuckDB' if sample_mode else 'Zetaris JDBC'}</p>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Agent team**")
    st.markdown(f"Planner + SQL investigator · {'Meterless Nightshift' if has_token else 'Nemotron / offline'}  \nIndependent skeptic · {'NVIDIA Nemotron' if has_nvidia else 'offline reviewer'}  \nExplainer · {'Meterless Nightshift' if has_token else 'Nemotron / offline'}")
    if not has_token or not has_nvidia:
        st.info("For the full live multi-agent team, add Meterless `METERLESS_RUNTIME_TOKEN`, `METERLESS_BASE_URL`, `FAST_MODEL`, `DEEP_MODEL` and NVIDIA `NVIDIA_API_KEY` in Streamlit Secrets. Keep `SAMPLE_MODE = \"true\"` to use DuckDB sample data.")
        st.markdown("[Get a Nemotron API key ↗](https://build.nvidia.com/nvidia/nemotron-3_5-bolt-e4b)")
    st.caption("Model calls and query steps are logged under `logs/`.")
    with st.expander("2-minute screen-record flow"):
        st.markdown("**0:00** Introduce the revenue question.  \n**0:15** Click *Run the guided demo* and show the planner/query/reviewer status.  \n**0:55** Read the ranked, verified result.  \n**1:20** Expand the SQL evidence and show *Why do you believe this?*  \n**1:45** Close on the four-agent roles and the returns decoy.")

st.markdown("<div class='brandmark'>The agent that can explain why · Open Agent Hackathon</div><div class='hero'><div class='eyebrow'>Retail revenue intelligence</div><h1>Follow the change.<br><em>Find the why.</em></h1><p>Ask a retail revenue question. WhyTrace coordinates specialized agents, runs the queries, challenges the evidence, and verifies every number before it reaches the report.</p></div>", unsafe_allow_html=True)

st.markdown("<div class='section-title'>Start an investigation</div><div class='subtle'>Ask naturally about store revenue, product categories, returns, inventory, or monthly changes in the connected retail data. The examples are starting points; type your own question below.</div>", unsafe_allow_html=True)
st.markdown("<div class='process-rail'><span class='process-step'>01 &nbsp; PLAN</span><span class='process-arrow'>›</span><span class='process-step'>02 &nbsp; QUERY</span><span class='process-arrow'>›</span><span class='process-step'>03 &nbsp; CHALLENGE</span><span class='process-arrow'>›</span><span class='process-step'>04 &nbsp; VERIFY</span></div>", unsafe_allow_html=True)
guided_demo = st.button("▶  Load the 2-minute demo question", key="guided-demo", width="stretch")
if guided_demo:
    st.session_state["question_input"] = "Why did S3 revenue drop in March 2026?"
examples = ["Why did S3 revenue drop in March 2026?", "What drove the March revenue change?", "Did returns explain the March decline?"]
cols = st.columns(3)
for idx, (col, example) in enumerate(zip(cols, examples)):
    if col.button(example, key=f"example-{idx}", width="stretch"):
        st.session_state["question_input"] = example
with st.form("investigation", border=False):
    question = st.text_input("Your question", key="question_input", placeholder="Ask about any store, item, category, returns, inventory, or revenue movement…")
    submitted = st.form_submit_button("Investigate with WhyTrace  →", type="primary", width="stretch")
if submitted and question.strip():
    try:
        with st.status("Agent team is thinking through your question...", expanded=True) as progress:
            st.session_state["report"] = run_agent(question.strip(), on_step=progress.write)
            progress.update(label="Investigation complete · evidence verified", state="complete", expanded=True)
            st.session_state.pop("provenance", None)
    except Exception as exc:
        st.error(f"The investigation could not complete: {exc}")

report = st.session_state.get("report")
if report:
    st.divider()
    ai_mode = not report["agent_mode"].lower().startswith("offline") and "fallback" not in report["agent_mode"].lower()
    st.markdown(f"<span class='status {'ai' if ai_mode else 'offline'}'>{'Nightshift AI analysis' if ai_mode else 'Deterministic evidence analysis'}</span> &nbsp; <span class='subtle'>Question · {report['question']}</span>", unsafe_allow_html=True)
    st.markdown("<div class='section-title' style='margin-top:.85rem'>Investigation result</div>", unsafe_allow_html=True)
    if report.get("explanation"):
        st.markdown(f"<div class='panel claim'>{report['explanation']}<div class='subtle' style='margin-top:.7rem;font-size:.78rem'>Explanation model · {report['explanation_model']} · Sources are linked below</div></div>", unsafe_allow_html=True)
    if report.get("skeptic_review"):
        review = report["skeptic_review"]
        with st.container(border=True):
            st.markdown("**Independent skeptic review**")
            st.write(review["review"])
            st.caption(f"Reviewer · {review['model']} · {len(review['evidence_ids'])} evidence sources in scope")
            if review.get("contradictions"):
                st.warning(f"Skeptic flagged {len(review['contradictions'])} possible contradiction(s). Inspect cited rows before relying on the conclusion.")
            else:
                st.success("No unsupported number or conflicting row found in the independent review.")
    if report["ranked_drivers"]:
        main = report["ranked_drivers"][0]
        metrics = st.columns(3)
        metrics[0].metric("Lead signal", main.get("subject", main.get("store_id", "Revenue")))
        metrics[1].metric("Focus period", main.get("period", "—"))
        metrics[2].metric("Evidence check", "Verified" if main["verified"] else "Mismatch")
        for rank, claim in enumerate(report["ranked_drivers"], 1):
            with st.container(border=True):
                left, right = st.columns([5, 1])
                left.markdown(f"### {rank:02d} · {claim['title']}")
                right.markdown(f"<span class='status'>{'Verified' if claim['verified'] else 'Mismatch'}</span>", unsafe_allow_html=True)
                st.markdown(f"<div class='claim'>{claim['claim']}</div>", unsafe_allow_html=True)
                st.caption(f"Confidence {claim['confidence']:.0%} · SQL model {claim['model']}")
                if st.button("Why do you believe this?  ↓", key=f"why-{rank}"):
                    st.session_state["provenance"] = claim["evidence_ids"]
                for eid in claim["evidence_ids"]:
                    ev = WorldStoreService().get(eid)
                    if ev:
                        with st.expander(f"Evidence {eid} · {ev['row_count']} result rows"):
                            st.code(ev["sql"], language="sql")
                            st.dataframe(ev["rows"], width="stretch", hide_index=True)
    else:
        st.warning("The queries ran, but the available rows did not support a month-over-month driver. Open the evidence below to inspect the returned data.")

    if report.get("ruled_out"):
        st.markdown("<div class='section-title' style='margin-top:1.6rem'>Other signals checked</div><div class='subtle'>Alternative explanations stay visible with their supporting query evidence.</div>", unsafe_allow_html=True)
        for idx, claim in enumerate(report["ruled_out"]):
            with st.expander(f"{'✓' if claim['verified'] else '·'}  {claim['title']}  ·  {claim['model']}"):
                st.write(claim["claim"])
                st.caption("Verified cited values" if claim["verified"] else "A cited value did not match on recheck")
                if st.button("Show provenance chain", key=f"why-other-{idx}"):
                    st.session_state["provenance"] = claim["evidence_ids"]
                for eid in claim["evidence_ids"]:
                    ev = WorldStoreService().get(eid)
                    if ev:
                        st.code(ev["sql"], language="sql")
                        st.dataframe(ev["rows"], width="stretch", hide_index=True)

    if st.session_state.get("provenance"):
        st.markdown("<div class='section-title' style='margin-top:1.5rem'>Claim provenance</div>", unsafe_allow_html=True)
        for ev in report["context"]["provenance"]:
            if ev["evidence_id"] in st.session_state["provenance"]:
                st.markdown(f"**Claim → `{ev['evidence_id']}` → {ev['source']} → {ev['model']}**")
                st.code(ev["sql"], language="sql")
                evidence = WorldStoreService().get(ev["evidence_id"])
                if evidence:
                    st.dataframe(evidence["rows"], width="stretch", hide_index=True)

    st.markdown("<div class='section-title' style='margin-top:1.5rem'>Recommended next steps</div>", unsafe_allow_html=True)
    for idx, action in enumerate(report["recommended_actions"], 1):
        st.markdown(f"**{idx}.** {action}")
    with st.expander("Investigation trace · plan, SQL, models, row counts"):
        st.caption(f"Planning model · {report['model_plan']}")
        for step in report["hypotheses"]:
            st.markdown(f"**{step['name']}** · {step['model']} · {len(step['rows'])} rows")
            st.code(step["sql"], language="sql")
        st.markdown(f"**Independent skeptic** · {report['skeptic_review']['model']}")
        st.markdown(f"**Evidence explainer** · {report['explanation_model']}")
