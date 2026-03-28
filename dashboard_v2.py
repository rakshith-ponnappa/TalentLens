"""
dashboard.py  –  Collective Resume Screening Dashboard (Streamlit).

Tabs:
  1. Screen          –  Upload JD + resumes, run pipeline
  2. Agent Panel     –  Multi-agent evaluation with discussion
  3. History         –  All past screenings, sortable by date/month/year
  4. Analytics       –  Aggregate statistics, trends, grade distribution
  5. Interview Prep  –  Generated questionnaires per candidate

Run:  streamlit run dashboard.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, date
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Ensure local imports work
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from jd_analyzer import analyze_jd
from resume_parser import parse_resume
from scorer import score_candidate, rank_candidates, compute_skill_gap
from verifier import run_verification
from agents import evaluate_candidate, ConsensusResult
from history import (
    save_session, get_all_sessions, get_candidates_for_session,
    get_all_candidates, get_stats_summary, get_candidate_history,
    get_sessions_by_month, get_sessions_by_year,
)
from interview_gen import generate_questionnaire
from models import CandidateScore, JDCriteria

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Resume Screener Pro",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem; border-radius: 12px; margin-bottom: 1.5rem; color: white;
    }
    .main-header h1 { color: white; font-size: 2rem; margin: 0; }
    .main-header p { color: #a0aec0; margin: 0.3rem 0 0 0; font-size: 0.95rem; }
    .metric-card {
        background: linear-gradient(135deg, #1e293b, #334155);
        border-radius: 12px; padding: 1.2rem 1.5rem; color: white;
        text-align: center; border: 1px solid #475569;
    }
    .metric-card .value { font-size: 2.2rem; font-weight: 700; color: #38bdf8; }
    .metric-card .label { font-size: 0.85rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.05em; }
    .agent-card {
        background: linear-gradient(135deg, #1e293b, #2d3748);
        border-radius: 10px; padding: 1rem; margin: 0.5rem 0;
        border-left: 4px solid #3b82f6;
    }
    .agent-card.strong-hire { border-left-color: #10b981; }
    .agent-card.hire { border-left-color: #3b82f6; }
    .agent-card.lean-hire { border-left-color: #f59e0b; }
    .agent-card.no-hire { border-left-color: #ef4444; }
    .discussion-msg {
        padding: 0.5rem 1rem; margin: 0.3rem 0; border-radius: 8px;
        background: #1e293b; border-left: 3px solid #475569;
        font-size: 0.9rem;
    }
    .discussion-msg .agent-name { font-weight: 700; color: #38bdf8; }
    .section-header {
        border-left: 4px solid #3b82f6; padding-left: 12px;
        margin: 1.5rem 0 1rem 0; font-size: 1.2rem; font-weight: 700; color: #e2e8f0;
    }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%); }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    .stDataFrame thead th { background: #1e293b !important; color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <h1>📋 Resume Screener Pro</h1>
    <p>Multi-Agent Evaluation • Skills Matching • Background Verification • Historical Tracking • Interview Prep</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
for key, default in {
    "jd_criteria": None,
    "scores": [],
    "agent_results": {},
    "questionnaires": {},
    "jd_text": "",
    "last_session_id": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📄 Upload Job Description")
    jd_file = st.file_uploader("Upload JD (PDF/DOCX/TXT)", type=["pdf", "docx", "doc", "txt"], key="jd_upload")
    jd_paste = st.text_area("Or paste JD text:", height=100, key="jd_paste")

    st.markdown("---")
    st.markdown("### 👤 Upload Resumes")
    resume_files = st.file_uploader("Upload Resumes (multiple)", type=["pdf", "docx", "doc", "txt"],
                                     accept_multiple_files=True, key="resume_upload")

    st.markdown("---")
    run_verify = st.checkbox("Run Background Verification", value=True)
    run_agents = st.checkbox("Run Agent Panel Evaluation", value=True)
    run_btn = st.button("🚀 Screen Candidates", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### ⚙️ Scoring Weights")
    st.caption("Must sum to 100")
    w_req = st.slider("Required Skills", 0, 50, 35)
    w_pref = st.slider("Preferred Skills", 0, 30, 15)
    w_exp = st.slider("Experience", 0, 40, 25)
    w_edu = st.slider("Education", 0, 20, 10)
    w_cert = st.slider("Certifications", 0, 20, 10)
    w_sem = st.slider("Semantic Similarity", 0, 20, 5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _save_upload(uploaded_file) -> Path:
    tmp = Path(__file__).parent / "data" / ".tmp"
    tmp.mkdir(exist_ok=True)
    p = tmp / uploaded_file.name
    p.write_bytes(uploaded_file.read())
    uploaded_file.seek(0)
    return p


def _grade_color(grade: str) -> str:
    return {"A+": "#10b981", "A": "#10b981", "B+": "#3b82f6", "B": "#3b82f6",
            "C": "#f59e0b", "D": "#f97316", "F": "#ef4444"}.get(grade, "#94a3b8")


def _rec_class(rec: str) -> str:
    if "Strong" in rec: return "strong-hire"
    if rec == "Hire": return "hire"
    if "Lean" in rec: return "lean-hire"
    return "no-hire"


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------
if run_btn:
    cfg = load_config()
    cfg.weights.required_skills = w_req
    cfg.weights.preferred_skills = w_pref
    cfg.weights.experience = w_exp
    cfg.weights.education = w_edu
    cfg.weights.certifications = w_cert
    cfg.weights.semantic = w_sem

    jd_source = None
    if jd_file:
        jd_source = str(_save_upload(jd_file))
    elif jd_paste.strip():
        jd_source = jd_paste.strip()
    else:
        st.error("Please upload a JD file or paste JD text.")
        st.stop()

    with st.spinner("📄 Analyzing Job Description…"):
        jd = analyze_jd(jd_source, cfg)
        st.session_state.jd_criteria = jd
        st.session_state.jd_text = jd.raw_text[:500]

    if not resume_files:
        st.error("Please upload at least one resume.")
        st.stop()

    # Parse resumes
    candidates = []
    progress = st.progress(0, text="Parsing resumes…")
    for i, rf in enumerate(resume_files):
        try:
            p = _save_upload(rf)
            candidates.append(parse_resume(str(p), cfg))
        except Exception as e:
            st.warning(f"Failed to parse {rf.name}: {e}")
        progress.progress((i + 1) / len(resume_files), text=f"Parsed {i+1}/{len(resume_files)}")
    progress.empty()

    if not candidates:
        st.error("No resumes parsed successfully.")
        st.stop()

    # Verify
    verifications = {}
    if run_verify:
        progress = st.progress(0, text="Running background verification…")
        for i, cand in enumerate(candidates):
            try:
                verifications[cand.name] = run_verification(cand, cfg)
            except Exception:
                pass
            progress.progress((i + 1) / len(candidates), text=f"Verified {i+1}/{len(candidates)}")
        progress.empty()

    # Score
    scores = []
    for cand in candidates:
        ver = verifications.get(cand.name)
        scores.append(score_candidate(cand, jd, ver, cfg))
    ranked = rank_candidates(scores)
    st.session_state.scores = ranked

    # Agent evaluation
    agent_results = {}
    if run_agents:
        progress = st.progress(0, text="Running agent panel evaluation…")
        for i, s in enumerate(ranked):
            try:
                agent_results[s.candidate.name] = evaluate_candidate(
                    s.candidate, jd, s, s.verification)
            except Exception as e:
                st.warning(f"Agent eval failed for {s.candidate.name}: {e}")
            progress.progress((i + 1) / len(ranked), text=f"Agent eval {i+1}/{len(ranked)}")
        progress.empty()
    st.session_state.agent_results = agent_results

    # Generate interview questionnaires
    questionnaires = {}
    for s in ranked:
        try:
            consensus = agent_results.get(s.candidate.name)
            questionnaires[s.candidate.name] = generate_questionnaire(s.candidate, jd, s, consensus)
        except Exception:
            pass
    st.session_state.questionnaires = questionnaires

    # Save to history
    try:
        session_id = save_session(jd, ranked, agent_results)
        st.session_state.last_session_id = session_id
    except Exception as e:
        st.warning(f"History save failed: {e}")

    st.success(f"✅ Screened {len(ranked)} candidate(s) | Agent Panel: {len(agent_results)} evaluated | Session saved")


# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
jd = st.session_state.jd_criteria
scores = st.session_state.scores
agent_results = st.session_state.agent_results
questionnaires = st.session_state.questionnaires

tab_screen, tab_agents, tab_history, tab_analytics, tab_interview = st.tabs([
    "📊 Screening Results", "🤖 Agent Panel", "📅 History", "📈 Analytics", "❓ Interview Prep"
])


# =====================================================================
# TAB 1: SCREENING RESULTS
# =====================================================================
with tab_screen:
    if jd:
        st.markdown('<div class="section-header">📋 Job Description Summary</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="metric-card"><div class="value">{len(jd.required_skills)}</div><div class="label">Required Skills</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="metric-card"><div class="value">{jd.min_experience_years:.0f}+</div><div class="label">Min Experience</div></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="metric-card"><div class="value">{jd.role_level}</div><div class="label">Role Level</div></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="metric-card"><div class="value">{jd.education_level}</div><div class="label">Education</div></div>', unsafe_allow_html=True)

        with st.expander("View Full JD Details"):
            st.write(f"**Title:** {jd.title}")
            st.write(f"**Industry:** {jd.industry}")
            st.write(f"**Required Skills:** {', '.join(jd.required_skills)}")
            st.write(f"**Preferred Skills:** {', '.join(jd.preferred_skills)}")

    if scores:
        st.markdown("---")
        st.markdown('<div class="section-header">📊 Screening Overview</div>', unsafe_allow_html=True)
        top = scores[0]
        ov1, ov2, ov3, ov4, ov5 = st.columns(5)
        with ov1: st.metric("Total Candidates", len(scores))
        with ov2: st.metric("Avg Score", f"{sum(s.overall_score for s in scores)/len(scores):.1f}")
        with ov3: st.metric("A/A+ Grade", sum(1 for s in scores if s.grade.startswith("A")))
        with ov4: st.metric("Top Candidate", top.candidate.name)
        with ov5: st.metric("Top Score", f"{top.overall_score:.1f}")

        # Rankings table
        st.markdown('<div class="section-header">🏆 Candidate Rankings</div>', unsafe_allow_html=True)
        rows = []
        for s in scores:
            req_total = len(s.matched_required_skills) + len(s.missing_required_skills)
            req_match = len(s.matched_required_skills)
            li = s.verification.linkedin
            li_status = "✅" if (li and li.url_resolves) else "⚠️" if (li and li.url) else "❌"
            consensus = agent_results.get(s.candidate.name)
            agent_rec = consensus.consensus_recommendation if consensus else "N/A"

            rows.append({
                "Rank": s.rank, "Candidate": s.candidate.name,
                "Score": f"{s.overall_score:.1f}", "Grade": s.grade,
                "Skills": f"{req_match}/{req_total}",
                "Exp": f"{s.candidate.total_experience_years:.1f}y",
                "Trust": f"{s.verification.overall_trust_score:.0%}",
                "LinkedIn": li_status, "Agent Rec": agent_rec,
                "Email": s.candidate.email,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Stacked bar chart
        if len(scores) > 1:
            st.markdown('<div class="section-header">📈 Score Comparison</div>', unsafe_allow_html=True)
            fig_bar = go.Figure()
            names = [s.candidate.name for s in scores]
            for attr, label, color in [
                ("required_skills", "Required Skills", "#3b82f6"),
                ("preferred_skills", "Preferred Skills", "#8b5cf6"),
                ("experience", "Experience", "#06b6d4"),
                ("education", "Education", "#10b981"),
                ("certifications", "Certifications", "#f59e0b"),
                ("semantic_similarity", "Semantic", "#ef4444"),
            ]:
                fig_bar.add_trace(go.Bar(
                    x=names, y=[getattr(s.breakdown, attr) for s in scores],
                    name=label, marker_color=color,
                ))
            fig_bar.update_layout(barmode="stack", template="plotly_dark",
                                   paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   height=400, margin=dict(l=40, r=40, t=40, b=40),
                                   legend=dict(orientation="h", y=-0.15))
            st.plotly_chart(fig_bar, use_container_width=True)

        # Candidate detail cards
        st.markdown('<div class="section-header">👤 Candidate Details</div>', unsafe_allow_html=True)
        for s in scores:
            medal = "🥇" if s.rank == 1 else "🥈" if s.rank == 2 else "🥉" if s.rank == 3 else "👤"
            with st.expander(f"{medal} #{s.rank} — {s.candidate.name} | {s.overall_score:.1f}/100 | {s.grade}", expanded=(s.rank == 1)):
                ic1, ic2, ic3 = st.columns(3)
                with ic1:
                    st.write(f"📧 **Email:** {s.candidate.email or 'N/A'}")
                    st.write(f"📱 **Phone:** {s.candidate.phone or 'N/A'}")
                with ic2:
                    st.write(f"📍 **Location:** {s.candidate.location or 'N/A'}")
                    st.write(f"🕐 **Experience:** {s.candidate.total_experience_years:.1f} years")
                with ic3:
                    li_url = s.candidate.linkedin_url or (s.verification.linkedin.url if s.verification.linkedin else "")
                    st.write(f"🔗 **LinkedIn:** {li_url or 'Not found'}")
                    st.write(f"🐙 **GitHub:** {s.candidate.github_url or 'N/A'}")

                st.markdown("---")

                # Radar chart + score table
                rc1, rc2 = st.columns(2)
                with rc1:
                    st.markdown("**Score Breakdown**")
                    b = s.breakdown
                    cats = ["Required", "Preferred", "Experience", "Education", "Certs", "Semantic"]
                    maxes = [w_req, w_pref, w_exp, w_edu, w_cert, w_sem]
                    vals = [b.required_skills, b.preferred_skills, b.experience, b.education, b.certifications, b.semantic_similarity]
                    pcts = [v / m * 100 if m > 0 else 0 for v, m in zip(vals, maxes)]
                    fig_r = go.Figure()
                    fig_r.add_trace(go.Scatterpolar(
                        r=pcts + [pcts[0]], theta=cats + [cats[0]],
                        fill="toself", fillcolor="rgba(59,130,246,0.2)",
                        line=dict(color="#3b82f6", width=2),
                    ))
                    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], showticklabels=False)),
                                         showlegend=False, template="plotly_dark",
                                         paper_bgcolor="rgba(0,0,0,0)", height=280,
                                         margin=dict(l=60, r=60, t=20, b=20))
                    st.plotly_chart(fig_r, use_container_width=True)
                with rc2:
                    st.markdown("**Score Points**")
                    score_df = pd.DataFrame({
                        "Category": cats, "Points": vals, "Max": maxes,
                        "%": [f"{p:.0f}%" for p in pcts],
                    })
                    st.dataframe(score_df, hide_index=True, use_container_width=True)
                    st.markdown(f"**Total: {s.overall_score:.1f} / 100**")

                    # Skill gap
                    if jd:
                        gap = compute_skill_gap(s.candidate.skills, s.candidate.raw_text, jd)
                        severity_color = {"Critical": "🔴", "Moderate": "🟡", "Low": "🟢"}.get(gap["gap_severity"], "⚪")
                        st.markdown(f"**Skill Gap:** {severity_color} {gap['gap_severity']} ({gap['required_match_pct']}% req match)")

                # Skills
                sk1, sk2 = st.columns(2)
                with sk1:
                    st.markdown("**✅ Matched Required Skills**")
                    st.success(", ".join(s.matched_required_skills) if s.matched_required_skills else "None")
                with sk2:
                    st.markdown("**❌ Missing Required Skills**")
                    if s.missing_required_skills:
                        st.error(", ".join(s.missing_required_skills))
                    else:
                        st.success("All matched!")

                # Verification
                st.markdown("---")
                vc1, vc2, vc3 = st.columns(3)
                with vc1:
                    st.markdown("**🏢 Companies**")
                    for co in s.verification.companies:
                        st.write(f"{'✅' if co.found else '❌'} **{co.name}** ({co.company_type}, {co.legitimacy_score:.0%})")
                with vc2:
                    st.markdown("**🔗 LinkedIn**")
                    li = s.verification.linkedin
                    if li:
                        if li.url_resolves: st.write(f"✅ Verified ({li.authenticity_score:.0%})")
                        elif li.url: st.write(f"⚠️ Found: {li.url}")
                        else: st.write("❌ Not found")
                    st.markdown("**🆔 Identity**")
                    ident = s.verification.identity
                    if ident:
                        st.write(f"Score: **{ident.overall_identity_score:.0%}** ({ident.method})")
                with vc3:
                    st.markdown("**📧 Email**")
                    if ident and ident.email:
                        em = ident.email
                        st.write(f"{'✅' if em.format_valid else '❌'} Format | {'✅' if em.mx_record_exists else '❌'} MX | {em.domain_type}")
                    st.markdown("**📅 Timeline**")
                    if ident and ident.timeline:
                        tl = ident.timeline
                        st.write(f"{'✅' if tl.timeline_plausible else '⚠️'} {tl.calculated_years:.1f} yrs calculated")
                        for gap in tl.gap_details:
                            st.warning(gap)

        # Export button
        st.markdown("---")
        if st.button("📥 Download JSON Report"):
            from report_generator import _score_to_dict
            data = {
                "generated_at": datetime.now().isoformat(),
                "job_title": jd.title if jd else "",
                "candidates": [_score_to_dict(s) for s in scores],
            }
            st.download_button("Download", json.dumps(data, indent=2, default=str),
                                file_name="screening_report.json", mime="application/json")

    elif not jd:
        st.markdown("""
        <div style="text-align: center; padding: 3rem;">
            <h2 style="color: #64748b;">Welcome to Resume Screener Pro</h2>
            <p style="color: #94a3b8;">Upload a JD and resumes in the sidebar to begin screening.</p>
        </div>
        """, unsafe_allow_html=True)


# =====================================================================
# TAB 2: AGENT PANEL
# =====================================================================
with tab_agents:
    if not agent_results:
        st.info("Run screening with 'Agent Panel Evaluation' enabled to see results here.")
    else:
        st.markdown('<div class="section-header">🤖 Multi-Agent Evaluation Panel</div>', unsafe_allow_html=True)
        st.caption("5 specialist agents evaluate each candidate from their unique perspective, then reach consensus.")

        selected_candidate = st.selectbox(
            "Select Candidate",
            options=list(agent_results.keys()),
            key="agent_candidate_select",
        )

        if selected_candidate and selected_candidate in agent_results:
            consensus: ConsensusResult = agent_results[selected_candidate]

            # Consensus summary
            st.markdown("### 🎯 Consensus")
            cc1, cc2, cc3, cc4 = st.columns(4)
            with cc1:
                st.markdown(f'<div class="metric-card"><div class="value">{consensus.consensus_score}</div><div class="label">Consensus Score</div></div>', unsafe_allow_html=True)
            with cc2:
                st.markdown(f'<div class="metric-card"><div class="value" style="color: {_grade_color(consensus.consensus_grade)}">{consensus.consensus_grade}</div><div class="label">Grade</div></div>', unsafe_allow_html=True)
            with cc3:
                st.markdown(f'<div class="metric-card"><div class="value" style="font-size:1.2rem">{consensus.consensus_recommendation}</div><div class="label">Recommendation</div></div>', unsafe_allow_html=True)
            with cc4:
                st.markdown(f'<div class="metric-card"><div class="value">{consensus.confidence:.0%}</div><div class="label">Confidence</div></div>', unsafe_allow_html=True)

            st.markdown(consensus.summary)

            if consensus.risk_flags:
                st.markdown("**Risk Flags:**")
                for flag in consensus.risk_flags:
                    st.warning(flag)

            st.markdown("---")

            # Individual agent evaluations
            st.markdown("### 👥 Agent Evaluations")
            for ev in consensus.evaluations:
                rec_cls = _rec_class(ev.recommendation)
                with st.expander(f"{'🏗️' if 'Architect' in ev.agent_name and 'App' in ev.agent_name else '📦' if 'Product' in ev.agent_name else '🔒' if 'Security' in ev.agent_name else '🧪' if 'QA' in ev.agent_name else '⚙️'} {ev.agent_name} — {ev.score}/100 ({ev.grade}) — {ev.recommendation}"):
                    ae1, ae2 = st.columns(2)
                    with ae1:
                        st.markdown("**Strengths:**")
                        for s_item in ev.strengths:
                            st.write(f"✅ {s_item}")
                    with ae2:
                        st.markdown("**Concerns:**")
                        for c_item in ev.concerns:
                            st.write(f"⚠️ {c_item}")

                    if ev.skill_gaps:
                        st.markdown(f"**Skill Gaps:** {', '.join(ev.skill_gaps)}")

                    if ev.key_questions:
                        st.markdown("**Interview Questions:**")
                        for q in ev.key_questions:
                            st.write(f"❓ {q}")

                    st.caption(ev.rationale)

            # Agent score comparison radar
            st.markdown("### 📊 Agent Score Comparison")
            agent_names = [ev.agent_name for ev in consensus.evaluations]
            agent_scores = [ev.score for ev in consensus.evaluations]

            fig_agent = go.Figure()
            fig_agent.add_trace(go.Scatterpolar(
                r=agent_scores + [agent_scores[0]],
                theta=agent_names + [agent_names[0]],
                fill="toself", fillcolor="rgba(56,189,248,0.2)",
                line=dict(color="#38bdf8", width=2),
                name=selected_candidate,
            ))
            fig_agent.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                height=350, margin=dict(l=80, r=80, t=30, b=30),
            )
            st.plotly_chart(fig_agent, use_container_width=True)

            # Discussion log
            st.markdown("### 💬 Agent Discussion")
            for msg in consensus.discussion:
                round_label = f"Round {msg.round_number}"
                st.markdown(
                    f'<div class="discussion-msg">'
                    f'<span class="agent-name">{msg.agent_name}</span> '
                    f'<span style="color:#64748b">({round_label})</span><br/>'
                    f'{msg.message}</div>',
                    unsafe_allow_html=True,
                )

            # Interview focus areas
            if consensus.interview_focus_areas:
                st.markdown("### 🎯 Recommended Interview Focus Areas")
                for i, q in enumerate(consensus.interview_focus_areas, 1):
                    st.write(f"{i}. {q}")


# =====================================================================
# TAB 3: HISTORY
# =====================================================================
with tab_history:
    st.markdown('<div class="section-header">📅 Screening History</div>', unsafe_allow_html=True)

    # Date filter
    hc1, hc2, hc3 = st.columns(3)
    with hc1:
        filter_type = st.selectbox("Filter by:", ["All", "Month", "Year"], key="hist_filter")
    with hc2:
        if filter_type == "Month":
            selected_year = st.number_input("Year", min_value=2024, max_value=2030,
                                             value=datetime.now().year, key="hist_year")
            selected_month = st.number_input("Month", min_value=1, max_value=12,
                                              value=datetime.now().month, key="hist_month")
        elif filter_type == "Year":
            selected_year = st.number_input("Year", min_value=2024, max_value=2030,
                                             value=datetime.now().year, key="hist_year_only")
    with hc3:
        search_name = st.text_input("Search candidate:", key="hist_search")

    # Fetch data
    try:
        if filter_type == "Month":
            sessions = get_sessions_by_month(selected_year, selected_month)
        elif filter_type == "Year":
            sessions = get_sessions_by_year(selected_year)
        else:
            sessions = get_all_sessions()
    except Exception:
        sessions = []

    if sessions:
        st.markdown(f"**{len(sessions)} screening session(s) found**")

        sess_rows = []
        for sess in sessions:
            sess_rows.append({
                "ID": sess["id"],
                "Date": sess["created_at"],
                "JD Title": sess["jd_title"],
                "Role": sess["jd_role"],
                "Candidates": sess["total_candidates"],
                "Avg Score": f"{sess['avg_score']:.1f}",
                "Top": sess["top_candidate"],
                "Top Score": f"{sess['top_score']:.1f}",
            })
        st.dataframe(pd.DataFrame(sess_rows), use_container_width=True, hide_index=True)

        # Session detail
        selected_session = st.selectbox(
            "View session details:",
            options=[s["id"] for s in sessions],
            format_func=lambda x: f"Session {x} — {next((s['jd_title'] for s in sessions if s['id']==x), '')}",
            key="hist_session_select",
        )

        if selected_session:
            try:
                cands = get_candidates_for_session(selected_session)
            except Exception:
                cands = []

            if cands:
                st.markdown(f"### Candidates in Session {selected_session}")
                for cand in cands:
                    with st.expander(f"#{cand['rank']} — {cand['name']} | {cand['overall_score']}/100 | {cand['grade']}"):
                        dc1, dc2, dc3 = st.columns(3)
                        with dc1:
                            st.write(f"📧 {cand['email']}")
                            st.write(f"📱 {cand['phone']}")
                            st.write(f"📍 {cand['location']}")
                        with dc2:
                            st.write(f"🕐 {cand['experience_years']:.1f} years")
                            st.write(f"🔗 {cand['linkedin'] or 'N/A'}")
                            st.write(f"📁 {cand['source_file']}")
                        with dc3:
                            if isinstance(cand['breakdown'], dict):
                                for k, v in cand['breakdown'].items():
                                    st.write(f"**{k}:** {v}")

                        # Skills
                        if isinstance(cand['matched_required'], list) and cand['matched_required']:
                            st.success(f"✅ Matched: {', '.join(cand['matched_required'])}")
                        if isinstance(cand['missing_required'], list) and cand['missing_required']:
                            st.error(f"❌ Missing: {', '.join(cand['missing_required'])}")

                        # Agent consensus
                        if isinstance(cand['agent_consensus'], dict) and cand['agent_consensus']:
                            ac = cand['agent_consensus']
                            if 'consensus_score' in ac:
                                st.markdown(f"**Agent Consensus:** {ac.get('consensus_score', 'N/A')}/100 — "
                                           f"{ac.get('consensus_recommendation', 'N/A')} "
                                           f"(Confidence: {ac.get('confidence', 'N/A')})")
    else:
        st.info("No screening history yet. Run a screening session to start tracking.")

    # Candidate search
    if search_name:
        st.markdown("---")
        st.markdown(f"### 🔍 Search results for '{search_name}'")
        try:
            results = get_candidate_history(search_name)
        except Exception:
            results = []
        if results:
            for r in results:
                st.write(f"**{r['name']}** — Score: {r['overall_score']} ({r['grade']}) — "
                        f"JD: {r.get('jd_title', 'N/A')} — Date: {r.get('session_date', 'N/A')}")
        else:
            st.info("No candidates found.")


# =====================================================================
# TAB 4: ANALYTICS
# =====================================================================
with tab_analytics:
    st.markdown('<div class="section-header">📈 Screening Analytics</div>', unsafe_allow_html=True)

    try:
        stats = get_stats_summary()
    except Exception:
        stats = {"total_sessions": 0, "total_candidates": 0, "avg_score": 0,
                 "top_candidate": None, "grade_distribution": {}, "monthly_trend": []}

    # Overview metrics
    ac1, ac2, ac3, ac4 = st.columns(4)
    with ac1:
        st.markdown(f'<div class="metric-card"><div class="value">{stats["total_sessions"]}</div><div class="label">Total Sessions</div></div>', unsafe_allow_html=True)
    with ac2:
        st.markdown(f'<div class="metric-card"><div class="value">{stats["total_candidates"]}</div><div class="label">Total Candidates</div></div>', unsafe_allow_html=True)
    with ac3:
        st.markdown(f'<div class="metric-card"><div class="value">{stats["avg_score"]}</div><div class="label">Avg Score</div></div>', unsafe_allow_html=True)
    with ac4:
        top_c = stats.get("top_candidate")
        top_name = dict(top_c).get("name", "N/A") if top_c else "N/A"
        st.markdown(f'<div class="metric-card"><div class="value" style="font-size:1.2rem">{top_name}</div><div class="label">All-Time Top</div></div>', unsafe_allow_html=True)

    # Grade distribution
    grade_dist = stats.get("grade_distribution", {})
    if grade_dist:
        st.markdown("### Grade Distribution")
        grade_order = ["A+", "A", "B+", "B", "C", "D", "F"]
        grade_vals = [grade_dist.get(g, 0) for g in grade_order]
        grade_colors = ["#10b981", "#10b981", "#3b82f6", "#3b82f6", "#f59e0b", "#f97316", "#ef4444"]
        fig_grade = go.Figure(go.Bar(
            x=grade_order, y=grade_vals,
            marker_color=grade_colors,
            text=grade_vals, textposition="auto",
        ))
        fig_grade.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                 plot_bgcolor="rgba(0,0,0,0)", height=300,
                                 margin=dict(l=40, r=40, t=30, b=30))
        st.plotly_chart(fig_grade, use_container_width=True)

    # Monthly trend
    monthly = stats.get("monthly_trend", [])
    if monthly:
        st.markdown("### Monthly Screening Trend")
        months = [m["month"] for m in monthly]
        counts = [m["candidates"] for m in monthly]
        avgs = [round(m["avg_score"], 1) for m in monthly]

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Bar(x=months, y=counts, name="Candidates", marker_color="#3b82f6"))
        fig_trend.add_trace(go.Scatter(x=months, y=avgs, name="Avg Score",
                                        mode="lines+markers", yaxis="y2",
                                        line=dict(color="#f59e0b", width=2)))
        fig_trend.update_layout(
            template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            height=350, margin=dict(l=40, r=40, t=30, b=30),
            yaxis=dict(title="Candidates"), yaxis2=dict(title="Avg Score", overlaying="y", side="right"),
            legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    # All candidates table
    st.markdown("### 📋 All Scanned Candidates")
    try:
        all_cands = get_all_candidates()
    except Exception:
        all_cands = []

    if all_cands:
        cand_rows = []
        for c in all_cands:
            cand_rows.append({
                "Name": c["name"],
                "Score": c["overall_score"],
                "Grade": c["grade"],
                "Rank": c["rank"],
                "Experience": f"{c['experience_years']:.1f}y",
                "Email": c["email"],
                "JD": c.get("jd_title", ""),
                "Date": c.get("session_date", c.get("scanned_at", "")),
            })
        st.dataframe(pd.DataFrame(cand_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No candidates in history yet.")


# =====================================================================
# TAB 5: INTERVIEW PREP
# =====================================================================
with tab_interview:
    st.markdown('<div class="section-header">❓ Interview Questionnaire Generator</div>', unsafe_allow_html=True)

    if not questionnaires:
        st.info("Run a screening to generate interview questionnaires.")
    else:
        sel_cand = st.selectbox("Select Candidate:", options=list(questionnaires.keys()),
                                 key="interview_select")

        if sel_cand and sel_cand in questionnaires:
            q = questionnaires[sel_cand]
            st.markdown(q.summary)
            st.markdown(f"**Total Questions:** {q.total_questions} | **Skill Gaps Addressed:** {len(q.skill_gaps_addressed)}")

            if q.skill_gaps_addressed:
                st.warning(f"Skill gaps to probe: {', '.join(q.skill_gaps_addressed)}")

            for section_name, questions in q.sections.items():
                st.markdown(f"### {section_name} ({len(questions)} questions)")
                for i, qq in enumerate(questions, 1):
                    with st.expander(f"Q{i}: {qq.question[:80]}{'…' if len(qq.question) > 80 else ''}"):
                        st.markdown(f"**Question:** {qq.question}")
                        st.caption(f"**Rationale:** {qq.rationale}")
                        st.caption(f"**Difficulty:** {qq.difficulty} | **Target:** {qq.target_skill}")
                        if qq.suggested_followup:
                            st.caption(f"**Follow-up:** {qq.suggested_followup}")

            # Export questionnaire
            st.markdown("---")
            export_data = {
                "candidate": q.candidate_name,
                "role": q.role_title,
                "generated_at": q.generated_at,
                "total_questions": q.total_questions,
                "sections": {
                    sec: [{"question": qq.question, "rationale": qq.rationale,
                           "difficulty": qq.difficulty, "target_skill": qq.target_skill,
                           "followup": qq.suggested_followup} for qq in qs]
                    for sec, qs in q.sections.items()
                },
            }
            st.download_button(
                f"📥 Download Questionnaire for {sel_cand}",
                json.dumps(export_data, indent=2),
                file_name=f"interview_{sel_cand.replace(' ', '_')}.json",
                mime="application/json",
            )
