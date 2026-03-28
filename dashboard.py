"""
dashboard.py  –  Executive-grade resume screening dashboard (Streamlit).

Run:  streamlit run dashboard.py
"""
from __future__ import annotations

import sys
import time
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
from scorer import score_candidate, rank_candidates
from verifier import run_verification
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
# Custom CSS for executive look
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Main font */
    html, body, [class*="css"] {
        font-family: 'Inter', 'Segoe UI', sans-serif;
    }
    /* Header gradient */
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        color: white;
    }
    .main-header h1 {
        color: white;
        font-size: 2rem;
        margin: 0;
    }
    .main-header p {
        color: #a0aec0;
        margin: 0.3rem 0 0 0;
        font-size: 0.95rem;
    }
    /* Metric cards */
    .metric-card {
        background: linear-gradient(135deg, #1e293b, #334155);
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
        color: white;
        text-align: center;
        border: 1px solid #475569;
    }
    .metric-card .value {
        font-size: 2.2rem;
        font-weight: 700;
        color: #38bdf8;
    }
    .metric-card .label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    /* Status badges */
    .badge-pass {
        background: #065f46; color: #6ee7b7; padding: 2px 10px;
        border-radius: 12px; font-size: 0.8rem; font-weight: 600;
    }
    .badge-warn {
        background: #78350f; color: #fbbf24; padding: 2px 10px;
        border-radius: 12px; font-size: 0.8rem; font-weight: 600;
    }
    .badge-fail {
        background: #7f1d1d; color: #fca5a5; padding: 2px 10px;
        border-radius: 12px; font-size: 0.8rem; font-weight: 600;
    }
    .badge-grade {
        font-size: 1.5rem; font-weight: 800;
    }
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important;
    }
    /* Table header */
    .stDataFrame thead th {
        background: #1e293b !important;
        color: #e2e8f0 !important;
    }
    /* Section headers */
    .section-header {
        border-left: 4px solid #3b82f6;
        padding-left: 12px;
        margin: 1.5rem 0 1rem 0;
        font-size: 1.2rem;
        font-weight: 700;
        color: #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <h1>📋 Resume Screener Pro</h1>
    <p>AI-Powered Candidate Screening • Skills Matching • Background Verification • Executive Dashboard</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "jd_criteria" not in st.session_state:
    st.session_state.jd_criteria = None
if "scores" not in st.session_state:
    st.session_state.scores = []
if "jd_text" not in st.session_state:
    st.session_state.jd_text = ""


# ---------------------------------------------------------------------------
# Sidebar – Upload Phase
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 📄 Upload Job Description")
    jd_file = st.file_uploader(
        "Upload JD (PDF / DOCX / TXT)",
        type=["pdf", "docx", "doc", "txt"],
        key="jd_upload",
    )
    jd_paste = st.text_area("Or paste JD text:", height=120, key="jd_paste")

    st.markdown("---")
    st.markdown("### 👤 Upload Resumes")
    resume_files = st.file_uploader(
        "Upload Resumes (multiple)",
        type=["pdf", "docx", "doc", "txt"],
        accept_multiple_files=True,
        key="resume_upload",
    )

    st.markdown("---")
    run_verify = st.checkbox("Run Background Verification", value=True)
    run_btn = st.button("🚀 Screen Candidates", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### ⚙️ Scoring Weights")
    st.caption("Weights must sum to 100")
    w_req = st.slider("Required Skills", 0, 50, 35)
    w_pref = st.slider("Preferred Skills", 0, 30, 15)
    w_exp = st.slider("Experience", 0, 40, 25)
    w_edu = st.slider("Education", 0, 20, 10)
    w_cert = st.slider("Certifications", 0, 20, 10)
    w_sem = st.slider("Semantic Similarity", 0, 20, 5)


# ---------------------------------------------------------------------------
# Helper: save uploaded file to temp path
# ---------------------------------------------------------------------------
def _save_upload(uploaded_file) -> Path:
    tmp = Path(__file__).parent / "data" / ".tmp"
    tmp.mkdir(exist_ok=True)
    p = tmp / uploaded_file.name
    p.write_bytes(uploaded_file.read())
    uploaded_file.seek(0)
    return p


# ---------------------------------------------------------------------------
# Pipeline execution
# ---------------------------------------------------------------------------
if run_btn:
    cfg = load_config()

    # Override weights from sidebar
    cfg.weights.required_skills = w_req
    cfg.weights.preferred_skills = w_pref
    cfg.weights.experience = w_exp
    cfg.weights.education = w_edu
    cfg.weights.certifications = w_cert
    cfg.weights.semantic = w_sem

    # Parse JD
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
        progress.progress((i + 1) / len(resume_files), text=f"Parsed {i+1}/{len(resume_files)} resumes")
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
    st.success(f"✅ Screened {len(ranked)} candidate(s) successfully!")


# ---------------------------------------------------------------------------
# Dashboard display
# ---------------------------------------------------------------------------
jd = st.session_state.jd_criteria
scores = st.session_state.scores

if jd:
    # JD Summary
    st.markdown('<div class="section-header">📋 Job Description Summary</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""<div class="metric-card">
            <div class="value">{len(jd.required_skills)}</div>
            <div class="label">Required Skills</div>
        </div>""", unsafe_allow_html=True)
    with col2:
        st.markdown(f"""<div class="metric-card">
            <div class="value">{jd.min_experience_years:.0f}+</div>
            <div class="label">Min Experience (yrs)</div>
        </div>""", unsafe_allow_html=True)
    with col3:
        st.markdown(f"""<div class="metric-card">
            <div class="value">{jd.role_level}</div>
            <div class="label">Role Level</div>
        </div>""", unsafe_allow_html=True)
    with col4:
        st.markdown(f"""<div class="metric-card">
            <div class="value">{jd.education_level}</div>
            <div class="label">Education</div>
        </div>""", unsafe_allow_html=True)

    with st.expander("View Full JD Details", expanded=False):
        st.write(f"**Title:** {jd.title}")
        st.write(f"**Industry:** {jd.industry}")
        st.write(f"**Required Skills:** {', '.join(jd.required_skills)}")
        st.write(f"**Preferred Skills:** {', '.join(jd.preferred_skills)}")
        if jd.certifications_required:
            st.write(f"**Required Certs:** {', '.join(jd.certifications_required)}")


if scores:
    st.markdown("---")

    # Overview metrics
    st.markdown('<div class="section-header">📊 Screening Overview</div>', unsafe_allow_html=True)
    top = scores[0] if scores else None

    ov1, ov2, ov3, ov4, ov5 = st.columns(5)
    with ov1:
        st.metric("Total Candidates", len(scores))
    with ov2:
        avg_score = sum(s.overall_score for s in scores) / len(scores)
        st.metric("Avg Score", f"{avg_score:.1f}")
    with ov3:
        a_count = sum(1 for s in scores if s.grade.startswith("A"))
        st.metric("A/A+ Grade", a_count)
    with ov4:
        if top:
            st.metric("Top Candidate", top.candidate.name)
    with ov5:
        if top:
            st.metric("Top Score", f"{top.overall_score:.1f}")

    # -----------------------------------------------------------------------
    # Rankings Table
    # -----------------------------------------------------------------------
    st.markdown('<div class="section-header">🏆 Candidate Rankings</div>', unsafe_allow_html=True)

    rows = []
    for s in scores:
        req_total = len(s.matched_required_skills) + len(s.missing_required_skills)
        req_match = len(s.matched_required_skills)
        co_verified = sum(1 for c in s.verification.companies if c.found)
        co_total = len(s.verification.companies)

        li = s.verification.linkedin
        li_status = "✅ Verified" if (li and li.url_resolves) else "⚠️ Discovered" if (li and li.url) else "❌ None"

        ident = s.verification.identity
        id_score = f"{ident.overall_identity_score:.0%}" if ident else "N/A"

        rows.append({
            "Rank": s.rank,
            "Candidate": s.candidate.name,
            "Score": f"{s.overall_score:.1f}",
            "Grade": s.grade,
            "Skills Match": f"{req_match}/{req_total} ({req_match/max(req_total,1):.0%})",
            "Experience": f"{s.candidate.total_experience_years:.1f} yrs",
            "Trust": f"{s.verification.overall_trust_score:.0%}",
            "LinkedIn": li_status,
            "Identity": id_score,
            "Companies": f"{co_verified}/{co_total}",
            "Email": s.candidate.email,
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Rank": st.column_config.NumberColumn("Rank", width="small"),
            "Score": st.column_config.TextColumn("Score"),
            "Grade": st.column_config.TextColumn("Grade"),
        },
    )

    # -----------------------------------------------------------------------
    # Score comparison chart
    # -----------------------------------------------------------------------
    if len(scores) > 1:
        st.markdown('<div class="section-header">📈 Score Comparison</div>', unsafe_allow_html=True)

        fig_bar = go.Figure()
        names = [s.candidate.name for s in scores]
        fig_bar.add_trace(go.Bar(
            x=names,
            y=[s.breakdown.required_skills for s in scores],
            name="Required Skills",
            marker_color="#3b82f6",
        ))
        fig_bar.add_trace(go.Bar(
            x=names,
            y=[s.breakdown.preferred_skills for s in scores],
            name="Preferred Skills",
            marker_color="#8b5cf6",
        ))
        fig_bar.add_trace(go.Bar(
            x=names,
            y=[s.breakdown.experience for s in scores],
            name="Experience",
            marker_color="#06b6d4",
        ))
        fig_bar.add_trace(go.Bar(
            x=names,
            y=[s.breakdown.education for s in scores],
            name="Education",
            marker_color="#10b981",
        ))
        fig_bar.add_trace(go.Bar(
            x=names,
            y=[s.breakdown.certifications for s in scores],
            name="Certifications",
            marker_color="#f59e0b",
        ))
        fig_bar.add_trace(go.Bar(
            x=names,
            y=[s.breakdown.semantic_similarity for s in scores],
            name="Semantic Match",
            marker_color="#ef4444",
        ))
        fig_bar.update_layout(
            barmode="stack",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=400,
            margin=dict(l=40, r=40, t=40, b=40),
            legend=dict(orientation="h", y=-0.15),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # -----------------------------------------------------------------------
    # Candidate Detail Cards
    # -----------------------------------------------------------------------
    st.markdown('<div class="section-header">👤 Candidate Details</div>', unsafe_allow_html=True)

    for s in scores:
        with st.expander(f"{'🥇' if s.rank == 1 else '🥈' if s.rank == 2 else '🥉' if s.rank == 3 else '👤'} #{s.rank} — {s.candidate.name}  |  {s.overall_score:.1f}/100  |  Grade: {s.grade}", expanded=(s.rank == 1)):

            # Top-level candidate info
            info_col1, info_col2, info_col3 = st.columns(3)
            with info_col1:
                st.write(f"📧 **Email:** {s.candidate.email or 'N/A'}")
                st.write(f"📱 **Phone:** {s.candidate.phone or 'N/A'}")
            with info_col2:
                st.write(f"📍 **Location:** {s.candidate.location or 'N/A'}")
                st.write(f"🕐 **Experience:** {s.candidate.total_experience_years:.1f} years")
            with info_col3:
                li_url = s.candidate.linkedin_url or (s.verification.linkedin.url if s.verification.linkedin else "")
                st.write(f"🔗 **LinkedIn:** {li_url or 'Not found'}")
                st.write(f"🐙 **GitHub:** {s.candidate.github_url or 'N/A'}")

            st.markdown("---")

            # Score breakdown radar chart
            detail_c1, detail_c2 = st.columns([1, 1])
            with detail_c1:
                st.markdown("**Score Breakdown**")
                b = s.breakdown
                radar_cats = ["Required Skills", "Preferred", "Experience", "Education", "Certs", "Semantic"]
                radar_max = [w_req, w_pref, w_exp, w_edu, w_cert, w_sem]
                radar_vals = [b.required_skills, b.preferred_skills, b.experience, b.education, b.certifications, b.semantic_similarity]
                radar_pct = [v / m * 100 if m > 0 else 0 for v, m in zip(radar_vals, radar_max)]

                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=radar_pct + [radar_pct[0]],
                    theta=radar_cats + [radar_cats[0]],
                    fill="toself",
                    fillcolor="rgba(59, 130, 246, 0.2)",
                    line=dict(color="#3b82f6", width=2),
                    name=s.candidate.name,
                ))
                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 100], showticklabels=False),
                        bgcolor="rgba(0,0,0,0)",
                    ),
                    showlegend=False,
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    height=300,
                    margin=dict(l=60, r=60, t=30, b=30),
                )
                st.plotly_chart(fig_radar, use_container_width=True)

            with detail_c2:
                st.markdown("**Score Points**")
                score_data = {
                    "Category": ["Required Skills", "Preferred Skills", "Experience", "Education", "Certifications", "Semantic Sim"],
                    "Points": [b.required_skills, b.preferred_skills, b.experience, b.education, b.certifications, b.semantic_similarity],
                    "Max": [w_req, w_pref, w_exp, w_edu, w_cert, w_sem],
                }
                score_df = pd.DataFrame(score_data)
                score_df["%"] = (score_df["Points"] / score_df["Max"] * 100).round(0).astype(int).astype(str) + "%"
                st.dataframe(score_df, hide_index=True, use_container_width=True)
                st.markdown(f"**Total: {s.overall_score:.1f} / 100**")

            # Skills detail
            sk1, sk2 = st.columns(2)
            with sk1:
                st.markdown("**✅ Matched Required Skills**")
                if s.matched_required_skills:
                    st.success(", ".join(s.matched_required_skills))
                else:
                    st.warning("No matched skills")
            with sk2:
                st.markdown("**❌ Missing Required Skills**")
                if s.missing_required_skills:
                    st.error(", ".join(s.missing_required_skills))
                else:
                    st.success("All required skills matched!")

            # Verification section
            st.markdown("---")
            ver_c1, ver_c2, ver_c3 = st.columns(3)

            # Companies
            with ver_c1:
                st.markdown("**🏢 Company Verification**")
                for co in s.verification.companies:
                    icon = "✅" if co.found else "❌"
                    st.write(f"{icon} **{co.name}**")
                    st.caption(f"   {co.company_type} | {co.employee_count} | Score: {co.legitimacy_score:.0%}")
                    if co.notes:
                        st.caption(f"   {co.notes[:100]}")

            # LinkedIn + Identity
            with ver_c2:
                st.markdown("**🔗 LinkedIn Verification**")
                li = s.verification.linkedin
                if li:
                    if li.url_resolves:
                        st.write(f"✅ Profile verified")
                        st.write(f"   Authenticity: {li.authenticity_score:.0%}")
                    elif li.url:
                        st.write(f"⚠️ URL found but not verified")
                    else:
                        st.write(f"❌ No profile found")
                    if li.notes:
                        st.caption(li.notes[:150])
                    for flag in (li.red_flags or []):
                        st.warning(flag)

                st.markdown("**🆔 Identity Score**")
                ident = s.verification.identity
                if ident:
                    st.write(f"Overall: **{ident.overall_identity_score:.0%}** ({ident.method})")

            # Email + Education + Timeline
            with ver_c3:
                st.markdown("**📧 Email Verification**")
                if ident and ident.email:
                    em = ident.email
                    st.write(f"{'✅' if em.format_valid else '❌'} Format | {'✅' if em.mx_record_exists else '❌'} MX | {em.domain_type}")
                    st.caption(f"Domain: {em.domain}")

                st.markdown("**🎓 Education**")
                if ident and ident.education:
                    for edu in ident.education:
                        icon = "✅" if edu.found_online else "❓"
                        st.write(f"{icon} {edu.institution} ({edu.source})")

                st.markdown("**📅 Timeline**")
                if ident and ident.timeline:
                    tl = ident.timeline
                    st.write(f"{'✅' if tl.timeline_plausible else '⚠️'} Plausible ({tl.calculated_years:.1f} yrs calc)")
                    for gap in tl.gap_details:
                        st.warning(gap)

            # Experience history
            if s.candidate.experience:
                st.markdown("**💼 Work History**")
                for exp in s.candidate.experience:
                    st.write(f"• **{exp.title}** at **{exp.company}** ({exp.start_date} – {exp.end_date}, {exp.duration_months} months)")

            # Certifications
            if s.verification.certifications:
                st.markdown("**📜 Certifications**")
                for cert in s.verification.certifications:
                    icon = "✅" if cert.found_in_registry else "❓"
                    st.write(f"{icon} {cert.name} — {cert.issuer}")


    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    st.markdown("---")
    if st.button("📥 Download JSON Report"):
        import json
        from report_generator import _score_to_dict
        data = {
            "generated_at": pd.Timestamp.now().isoformat(),
            "job_title": jd.title,
            "candidates": [_score_to_dict(s) for s in scores],
        }
        st.download_button(
            "Download",
            json.dumps(data, indent=2, default=str),
            file_name="screening_report.json",
            mime="application/json",
        )

elif not jd:
    # Welcome screen
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem;">
        <h2 style="color: #64748b;">Welcome to Resume Screener Pro</h2>
        <p style="color: #94a3b8; font-size: 1.1rem; max-width: 600px; margin: 1rem auto;">
            Upload a Job Description and one or more resumes using the sidebar.<br>
            The system will automatically extract skills, score candidates, verify backgrounds, and rank them.
        </p>
        <div style="display: flex; justify-content: center; gap: 2rem; margin-top: 2rem; flex-wrap: wrap;">
            <div class="metric-card" style="min-width: 180px;">
                <div class="value">📄</div>
                <div class="label">Upload JD</div>
            </div>
            <div class="metric-card" style="min-width: 180px;">
                <div class="value">👤</div>
                <div class="label">Upload Resumes</div>
            </div>
            <div class="metric-card" style="min-width: 180px;">
                <div class="value">🚀</div>
                <div class="label">Screen & Rank</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Features")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        st.markdown("**🎯 Skills Matching**")
        st.caption("170+ skill taxonomy, semantic similarity, required vs preferred")
    with f2:
        st.markdown("**🏢 Company Verification**")
        st.caption("60+ known companies DB, OpenCorporates, LinkedIn company pages")
    with f3:
        st.markdown("**🔗 LinkedIn Discovery**")
        st.caption("Auto-discover LinkedIn profiles by name, verify authenticity")
    with f4:
        st.markdown("**🆔 Identity Checks**")
        st.caption("Email verification, education check, timeline analysis, web presence")
