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
[data-testid="stSidebar"] [data-testid="stButton"] > button, [data-testid="stSidebar"] [data-testid="stButton"] > button * { background:#fff9e8 !important; color:#173d45 !important; border-color:rgba(23,61,69,.2) !important; text-align:left; }
[data-testid="stSidebar"] [data-testid="stButton"] > button { justify-content:flex-start; padding-left:1rem; }
[data-testid="stSidebar"] [data-testid="stButton"] > button[kind="primary"], [data-testid="stSidebar"] [data-testid="stButton"] > button[kind="primary"] * { background:#173d45 !important; color:#ffebaf !important; border-color:#173d45 !important; }
[data-testid="stSidebar"] [data-testid="stButton"] > button:hover, [data-testid="stSidebar"] [data-testid="stButton"] > button:hover * { background:#e5f3f1 !important; color:#173d45 !important; transform:translateX(2px); }
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

.hero-note { position:relative; z-index:1; display:inline-block; margin-top:1.2rem; padding:.65rem .9rem; border:1px solid rgba(76,157,176,.35); border-radius:999px; color:#347f90; font-weight:800; font-size:.8rem; background:rgba(255,253,245,.48); }
.landing-hero { padding-top:2.6rem; padding-bottom:2.7rem; } .landing-rail { margin-top:1rem; }
.feature-card,.recent-card,.empty-visual,.chart-panel,.visual-insight { background:var(--paper); border:1px solid var(--line); border-radius:18px; padding:1.35rem 1.5rem; animation:revealUp .55s cubic-bezier(.2,.7,.25,1) both; transition:transform .2s ease,box-shadow .2s ease,border-color .2s ease; }
.feature-card:hover,.visual-insight:hover { transform:translateY(-4px); border-color:#a8cfd3; box-shadow:0 14px 30px rgba(23,61,69,.09); }
.feature-index { color:#4c9db0; font-weight:800; font-size:.68rem; letter-spacing:.15em; } .feature-card h3,.visual-insight h3 { font-family:'DM Serif Display',Georgia,serif; color:var(--deep); font-size:1.35rem; margin:.85rem 0 .4rem; } .feature-card p,.visual-insight p,.recent-card p { color:var(--muted); line-height:1.6; margin-bottom:0; }
.feature-card:nth-child(2) { animation-delay:.1s; } .feature-card:nth-child(3) { animation-delay:.2s; } .recent-card { margin-top:1rem; background:#eff8f7; } .recent-card h3 { font-family:'DM Serif Display',Georgia,serif; color:var(--deep); margin:.3rem 0; }
.visual-hero { background:linear-gradient(120deg,#ffebaf,#fff4ce 58%,#dff1ef); } .empty-visual { text-align:center; padding:3rem 1rem; margin:1.3rem 0; } .empty-visual h2 { font-family:'DM Serif Display',Georgia,serif; color:var(--deep); } .empty-visual p { color:var(--muted); }
.visual-orb { margin:0 auto 1.1rem; width:72px; height:72px; border-radius:50%; display:grid; place-items:center; color:#fff4ce; font-size:2rem; background:radial-gradient(circle at 35% 30%,#8bc7c9,#4c9db0 65%,#286876); box-shadow:0 0 0 12px #e7f3ef,0 0 42px #a9d7d4; animation:orbitPulse 3s ease-in-out infinite; }
.chart-panel { margin-top:1rem; background:#173d45; border-color:#285761; color:#fffdf5; overflow:hidden; } .chart-heading { display:flex; justify-content:space-between; align-items:center; gap:1rem; } .chart-heading h2 { font-family:'DM Serif Display',Georgia,serif; color:#fff4ce; margin:0; font-size:1.65rem; } .chart-heading .eyebrow { color:#91cbd0; } .trend-chart { width:100%; margin-top:1.4rem; overflow:visible; } .gridline { stroke:rgba(255,255,255,.13); stroke-width:1; } .axis { fill:#b6d1cf; font:12px Manrope,sans-serif; } .series { fill:none; stroke-width:4; stroke-linecap:round; stroke-linejoin:round; stroke-dasharray:1400; stroke-dashoffset:1400; animation:drawLine 1.8s cubic-bezier(.4,0,.2,1) forwards; } .s3-series { stroke:#ffebaf; } .peer-series { stroke:#71c0c9; animation-delay:.18s; } .dot { stroke:#173d45; stroke-width:2; animation:dotIn .5s ease-out both; } .s3-dot { fill:#ffebaf; } .peer-dot { fill:#71c0c9; animation-delay:.7s; } .chart-legend { display:flex; gap:1.5rem; justify-content:center; color:#d9e8e3; font-size:.8rem; } .chart-legend span { display:flex; gap:.45rem; align-items:center; } .chart-legend i { width:9px; height:9px; border-radius:50%; display:inline-block; } .legend-s3 { background:#ffebaf; } .legend-peer { background:#71c0c9; } .visual-insight { display:flex; align-items:flex-start; gap:1rem; margin:.7rem 0; } .insight-rank { font-family:'DM Serif Display',Georgia,serif; color:#4c9db0; font-size:1.8rem; } .visual-insight h3 { margin:0 0 .3rem; }
@keyframes drawLine { to { stroke-dashoffset:0; } } @keyframes dotIn { from { opacity:0; transform:scale(.2); } to { opacity:1; transform:scale(1); } }
@media(max-width:700px) { .hero { padding:1.5rem; } .process-rail { overflow:auto; } .trend-chart { min-height:230px; } }

</style>
""", unsafe_allow_html=True)

st.session_state.setdefault("page", "Overview")

with st.sidebar:
    st.markdown("<div style='font-family:DM Serif Display,Georgia,serif;font-size:2rem;line-height:1;color:#fffdf5'>WhyTrace</div><div style='opacity:.82;margin-top:.4rem;font-size:.82rem'>Evidence-led retail intelligence</div>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Workspace**")
    for _page in ("Overview", "Investigate", "Visualizations"):
        if st.button(_page, key=f"nav-{_page}", type="primary" if st.session_state.get("page", "Overview") == _page else "secondary", width="stretch"):
            st.session_state["page"] = _page
            st.rerun()
    st.divider()
    has_token = bool(_setting("METERLESS_RUNTIME_TOKEN").strip())
    has_nvidia = bool(_setting("NVIDIA_API_KEY").strip())
    live_ai = has_token or has_nvidia
    provider_label = ("Nightshift + Nemotron configured" if has_token and has_nvidia else
                      "Nightshift configured" if has_token else "Nemotron configured" if has_nvidia else "Offline evidence agent")
    st.markdown(f"<span class='status {'ai' if live_ai else 'offline'}'>{provider_label}</span>", unsafe_allow_html=True)
    sample_mode = _setting("SAMPLE_MODE", "true").strip().lower() in {"1", "true", "yes", "on"}
    st.markdown(f"<p style='font-size:.82rem;margin-top:.7rem;opacity:.88'>Data source  |  {'Sample DuckDB' if sample_mode else 'Zetaris JDBC'}</p>", unsafe_allow_html=True)
    st.divider()
    st.markdown("**Agent team**")
    st.markdown(f"Planner + SQL investigator  |  {'Meterless Nightshift' if has_token else 'Nemotron / offline'}  \nIndependent skeptic  |  {'NVIDIA Nemotron' if has_nvidia else 'offline reviewer'}  \nExplainer  |  {'Meterless Nightshift' if has_token else 'Nemotron / offline'}")
    if not has_token or not has_nvidia:
        st.info("For the full live multi-agent team, add Meterless `METERLESS_RUNTIME_TOKEN`, `METERLESS_BASE_URL`, `FAST_MODEL`, `DEEP_MODEL` and NVIDIA `NVIDIA_API_KEY` in Streamlit Secrets. Keep `SAMPLE_MODE = \"true\"` to use DuckDB sample data.")
        st.markdown("[Get a Nemotron API key ->](https://build.nvidia.com/nvidia/nemotron-3_5-bolt-e4b)")
    st.caption("Model calls and query steps are logged under `logs/`.")
    with st.expander("2-minute screen-record flow"):
        st.markdown("**0:00** Introduce the revenue question.  \n**0:15** Click *Load the demo question*, then *Investigate with WhyTrace*.  \n**0:55** Read the ranked, verified result.  \n**1:20** Expand SQL evidence and show the provenance chain.  \n**1:45** Close on the agent roles and returns decoy.")

if st.session_state["page"] == "Overview":
    st.markdown("<div class='brandmark'>THE AGENT THAT CAN EXPLAIN WHY &middot; OPEN AGENT HACKATHON</div><div class='hero landing-hero'><div class='eyebrow'>Evidence-led retail intelligence</div><h1>Follow the change.<br><em>Find the why.</em></h1><p>WhyTrace turns a revenue question into a coordinated investigation: agents plan, query, challenge, and verify the answer against source data.</p><div class='hero-note'>&#10022; &nbsp; Every finding comes with the SQL and rows behind it.</div></div>", unsafe_allow_html=True)
    nav_left, nav_right = st.columns([1, 1])
    with nav_left:
        if st.button("Start an investigation  ->", type="primary", key="landing-investigate", width="stretch"):
            st.session_state["page"] = "Investigate"
            st.rerun()
    with nav_right:
        if st.button("Explore visualizations  ->", key="landing-visuals", width="stretch"):
            st.session_state["page"] = "Visualizations"
            st.rerun()
    st.markdown("<div class='section-title' style='margin-top:2rem'>A clear path from question to evidence</div><div class='subtle'>Your investigation stays idle until you submit a question.</div>", unsafe_allow_html=True)
    st.markdown("<div class='process-rail landing-rail'><span class='process-step'>01 &nbsp; PLAN</span><span class='process-arrow'>&rsaquo;</span><span class='process-step'>02 &nbsp; QUERY</span><span class='process-arrow'>&rsaquo;</span><span class='process-step'>03 &nbsp; CHALLENGE</span><span class='process-arrow'>&rsaquo;</span><span class='process-step'>04 &nbsp; VERIFY</span></div>", unsafe_allow_html=True)
    features = st.columns(3)
    for col, number, title, body in zip(features, ("01", "02", "03"), ("Ask in plain language", "Watch agents work", "Trace every claim"), ("Explore store, category, item, returns, or inventory changes.", "Planner, SQL investigator, skeptic, and explainer coordinate on one question.", "Open the exact query, result rows, model, and verification status behind each finding.")):
        with col:
            st.markdown(f"<div class='feature-card'><div class='feature-index'>{number} / WHYTRACE</div><h3>{title}</h3><p>{body}</p></div>", unsafe_allow_html=True)
    _existing = st.session_state.get("report")
    if _existing and _existing.get("ranked_drivers"):
        _lead = _existing["ranked_drivers"][0]
        st.markdown(f"<div class='recent-card'><div class='eyebrow'>LATEST VERIFIED INVESTIGATION</div><h3>{_lead['title']}</h3><p>{_lead['claim']}</p><span class='status'>{'Verified' if _lead.get('verified') else 'Mismatch'}</span></div>", unsafe_allow_html=True)

elif st.session_state["page"] == "Investigate":
    st.markdown("<div class='brandmark'>The agent that can explain why  |  Open Agent Hackathon</div><div class='hero'><div class='eyebrow'>Retail revenue intelligence</div><h1>Follow the change.<br><em>Find the why.</em></h1><p>Ask a retail revenue question. WhyTrace coordinates specialized agents, runs the queries, challenges the evidence, and verifies every number before it reaches the report.</p></div>", unsafe_allow_html=True)

    st.markdown("<div class='section-title'>Start an investigation</div><div class='subtle'>Ask naturally about store revenue, product categories, returns, inventory, or monthly changes in the connected retail data. The examples are starting points; type your own question below.</div>", unsafe_allow_html=True)
    st.markdown("<div class='process-rail'><span class='process-step'>01 &nbsp; PLAN</span><span class='process-arrow'>></span><span class='process-step'>02 &nbsp; QUERY</span><span class='process-arrow'>></span><span class='process-step'>03 &nbsp; CHALLENGE</span><span class='process-arrow'>></span><span class='process-step'>04 &nbsp; VERIFY</span></div>", unsafe_allow_html=True)
    guided_demo = st.button("PLAY  Load the 2-minute demo question", key="guided-demo", width="stretch")
    if guided_demo:
        st.session_state["question_input"] = "Why did S3 revenue drop in March 2026?"
    examples = ["Why did S3 revenue drop in March 2026?", "What drove the March revenue change?", "Did returns explain the March decline?"]
    cols = st.columns(3)
    for idx, (col, example) in enumerate(zip(cols, examples)):
        if col.button(example, key=f"example-{idx}", width="stretch"):
            st.session_state["question_input"] = example
    with st.form("investigation", border=False):
        question = st.text_input("Your question", key="question_input", placeholder="Ask about any store, item, category, returns, inventory, or revenue movement...")
        submitted = st.form_submit_button("Investigate with WhyTrace  ->", type="primary", width="stretch")
    if submitted and question.strip():
        try:
            with st.status("Agent team is thinking through your question...", expanded=True) as progress:
                st.session_state["report"] = run_agent(question.strip(), on_step=progress.write)
                progress.update(label="Investigation complete  |  evidence verified", state="complete", expanded=True)
                st.session_state.pop("provenance", None)
        except Exception as exc:
            st.error(f"The investigation could not complete: {exc}")

    report = st.session_state.get("report")
    if report:
        st.divider()
        ai_mode = not report["agent_mode"].lower().startswith("offline") and "fallback" not in report["agent_mode"].lower()
        st.markdown(f"<span class='status {'ai' if ai_mode else 'offline'}'>{'Nightshift AI analysis' if ai_mode else 'Deterministic evidence analysis'}</span> &nbsp; <span class='subtle'>Question  |  {report['question']}</span>", unsafe_allow_html=True)
        st.markdown("<div class='section-title' style='margin-top:.85rem'>Investigation result</div>", unsafe_allow_html=True)
        if report.get("explanation"):
            st.markdown(f"<div class='panel claim'>{report['explanation']}<div class='subtle' style='margin-top:.7rem;font-size:.78rem'>Explanation model  |  {report['explanation_model']}  |  Sources are linked below</div></div>", unsafe_allow_html=True)
        if report.get("skeptic_review"):
            review = report["skeptic_review"]
            with st.container(border=True):
                st.markdown("**Independent skeptic review**")
                st.write(review["review"])
                st.caption(f"Reviewer  |  {review['model']}  |  {len(review['evidence_ids'])} evidence sources in scope")
                if review.get("contradictions"):
                    st.warning(f"Skeptic flagged {len(review['contradictions'])} possible contradiction(s). Inspect cited rows before relying on the conclusion.")
                else:
                    st.success("No unsupported number or conflicting row found in the independent review.")
        if report["ranked_drivers"]:
            main = report["ranked_drivers"][0]
            metrics = st.columns(3)
            metrics[0].metric("Lead signal", main.get("subject", main.get("store_id", "Revenue")))
            metrics[1].metric("Focus period", main.get("period", "-"))
            metrics[2].metric("Evidence check", "Verified" if main["verified"] else "Mismatch")
            for rank, claim in enumerate(report["ranked_drivers"], 1):
                with st.container(border=True):
                    left, right = st.columns([5, 1])
                    left.markdown(f"### {rank:02d}  |  {claim['title']}")
                    right.markdown(f"<span class='status'>{'Verified' if claim['verified'] else 'Mismatch'}</span>", unsafe_allow_html=True)
                    st.markdown(f"<div class='claim'>{claim['claim']}</div>", unsafe_allow_html=True)
                    st.caption(f"Confidence {claim['confidence']:.0%}  |  SQL model {claim['model']}")
                    if st.button("Why do you believe this?  v", key=f"why-{rank}"):
                        st.session_state["provenance"] = claim["evidence_ids"]
                    for eid in claim["evidence_ids"]:
                        ev = WorldStoreService().get(eid)
                        if ev:
                            with st.expander(f"Evidence {eid}  |  {ev['row_count']} result rows"):
                                st.code(ev["sql"], language="sql")
                                st.dataframe(ev["rows"], width="stretch", hide_index=True)
        else:
            st.warning("The queries ran, but the available rows did not support a month-over-month driver. Open the evidence below to inspect the returned data.")

        if report.get("ruled_out"):
            st.markdown("<div class='section-title' style='margin-top:1.6rem'>Other signals checked</div><div class='subtle'>Alternative explanations stay visible with their supporting query evidence.</div>", unsafe_allow_html=True)
            for idx, claim in enumerate(report["ruled_out"]):
                with st.expander(f"{'OK' if claim['verified'] else ' | '}  {claim['title']}   |   {claim['model']}"):
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
                    st.markdown(f"**Claim -> `{ev['evidence_id']}` -> {ev['source']} -> {ev['model']}**")
                    st.code(ev["sql"], language="sql")
                    evidence = WorldStoreService().get(ev["evidence_id"])
                    if evidence:
                        st.dataframe(evidence["rows"], width="stretch", hide_index=True)

        st.markdown("<div class='section-title' style='margin-top:1.5rem'>Recommended next steps</div>", unsafe_allow_html=True)
        for idx, action in enumerate(report["recommended_actions"], 1):
            st.markdown(f"**{idx}.** {action}")
        with st.expander("Investigation trace  |  plan, SQL, models, row counts"):
            st.caption(f"Planning model  |  {report['model_plan']}")
            for step in report["hypotheses"]:
                st.markdown(f"**{step['name']}**  |  {step['model']}  |  {len(step['rows'])} rows")
                st.code(step["sql"], language="sql")
            st.markdown(f"**Independent skeptic**  |  {report['skeptic_review']['model']}")
            st.markdown(f"**Evidence explainer**  |  {report['explanation_model']}")

elif st.session_state["page"] == "Visualizations":
    st.markdown("<div class='brandmark'>WHYTRACE / EVIDENCE VISUALS</div><div class='hero visual-hero'><div class='eyebrow'>Signals, made visible</div><h1>See the shape<br><em>of the change.</em></h1><p>Charts here are built from the same query evidence as the written report. Run an investigation to animate its verified trend.</p></div>", unsafe_allow_html=True)
    _visual_report = st.session_state.get("report")
    if not _visual_report:
        st.markdown("<div class='empty-visual'><div class='visual-orb'>&#10022;</div><h2>Your evidence canvas is ready</h2><p>Start an investigation to populate the charts with verified retail data. Opening this page does not run queries.</p></div>", unsafe_allow_html=True)
        if st.button("Go to Investigate  ->", type="primary", key="visuals-investigate"):
            st.session_state["page"] = "Investigate"
            st.rerun()
    else:
        _trend = next((h for h in _visual_report.get("hypotheses", []) if h.get("rows") and {"store_id", "year", "month", "revenue"}.issubset(h["rows"][0])), None)
        _drivers = _visual_report.get("ranked_drivers", [])
        _metrics = st.columns(3)
        _metrics[0].metric("Verified drivers", len([c for c in _drivers if c.get("verified")]))
        _metrics[1].metric("Evidence queries", len(_visual_report.get("hypotheses", [])))
        _metrics[2].metric("Ruled-out signals", len(_visual_report.get("ruled_out", [])))
        if _trend:
            _rows = _trend["rows"]
            _periods = sorted({(int(r["year"]), int(r["month"])) for r in _rows})
            _s3 = [next((float(r["revenue"]) for r in _rows if str(r["store_id"]).upper() == "S3" and (int(r["year"]), int(r["month"])) == period), 0.0) for period in _periods]
            _peers = [sum(float(r["revenue"]) for r in _rows if str(r["store_id"]).upper() != "S3" and (int(r["year"]), int(r["month"])) == period) / max(1, sum(1 for r in _rows if str(r["store_id"]).upper() != "S3" and (int(r["year"]), int(r["month"])) == period)) for period in _periods]
            _w, _h, _pad = 840, 340, 48
            _max = max(_s3 + _peers + [1]) * 1.15
            _xs = [_pad + i * ((_w - 2 * _pad) / max(1, len(_periods) - 1)) for i in range(len(_periods))]
            def _points(values):
                return " ".join(f"{x:.1f},{_h-_pad-(v/_max)*(_h-2*_pad):.1f}" for x, v in zip(_xs, values))
            _labels = "".join(f"<text class='axis' x='{x:.1f}' y='{_h-12}' text-anchor='middle'>{year}-{month:02d}</text>" for x, (year, month) in zip(_xs, _periods))
            _dots = "".join(f"<circle class='dot s3-dot' cx='{x:.1f}' cy='{_h-_pad-(v/_max)*(_h-2*_pad):.1f}' r='5'><title>S3: ${v:,.0f}</title></circle><circle class='dot peer-dot' cx='{x:.1f}' cy='{_h-_pad-(peer/_max)*(_h-2*_pad):.1f}' r='5'><title>Peer average: ${peer:,.0f}</title></circle>" for x, v, peer in zip(_xs, _s3, _peers))
            _svg = f"<svg class='trend-chart' viewBox='0 0 {_w} {_h}' role='img' aria-label='S3 revenue compared with peer average'><line class='gridline' x1='{_pad}' y1='{_pad}' x2='{_w-_pad}' y2='{_pad}'/><line class='gridline' x1='{_pad}' y1='{(_h)/2}' x2='{_w-_pad}' y2='{(_h)/2}'/><line class='gridline' x1='{_pad}' y1='{_h-_pad}' x2='{_w-_pad}' y2='{_h-_pad}'/><polyline class='series peer-series' points='{_points(_peers)}'/><polyline class='series s3-series' points='{_points(_s3)}'/>{_dots}{_labels}</svg>"
            st.markdown(f"<div class='chart-panel'><div class='chart-heading'><div><div class='eyebrow'>QUERY-BACKED MONTHLY TREND</div><h2>S3 vs. peer stores</h2></div><span class='status'>{'Verified' if not _drivers or _drivers[0].get('verified') else 'Review'}</span></div>{_svg}<div class='chart-legend'><span><i class='legend-s3'></i>S3 revenue</span><span><i class='legend-peer'></i>Peer average</span></div></div>", unsafe_allow_html=True)
            _eid = _trend.get("evidence", {}).get("evidence_id")
            st.caption(f"Source query | {_eid or 'Evidence is linked in the investigation report'} | model {_trend.get('model', 'unknown')}")
        if _drivers:
            st.markdown("<div class='section-title' style='margin-top:1.6rem'>What the data says</div>", unsafe_allow_html=True)
            for _i, _claim in enumerate(_drivers, 1):
                st.markdown(f"<div class='visual-insight'><span class='insight-rank'>0{_i}</span><div><h3>{_claim['title']}</h3><p>{_claim['claim']}</p><span class='status'>{'Verified' if _claim.get('verified') else 'Mismatch'}</span></div></div>", unsafe_allow_html=True)
        if _visual_report.get("ruled_out"):
            with st.expander("Ruled-out signals | keep the decoy in view"):
                for _claim in _visual_report["ruled_out"]:
                    st.markdown(f"**{_claim['title']}**  |  {'Verified' if _claim.get('verified') else 'Mismatch'}  \n{_claim['claim']}")
                    for _eid in _claim.get("evidence_ids", []):
                        _ev = WorldStoreService().get(_eid)
                        if _ev:
                            st.caption(f"Evidence {_eid} | {_ev['source']} | {_ev['model']}")
                            st.code(_ev["sql"], language="sql")
