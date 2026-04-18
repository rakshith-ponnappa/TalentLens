"""
Page 4: Results & Rankings — Detailed candidate scores, drill-down, red flags.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

st.header("🏆 Results & Rankings")

if "scored_candidates" not in st.session_state:
    st.warning("No screening results yet. Go to **Screening** to process resumes.")
    st.stop()

scores = st.session_state["scored_candidates"]
red_flag_reports = st.session_state.get("red_flag_reports", {})
jd = st.session_state.get("jd_criteria")

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Candidates", len(scores))
with col2:
    avg = sum(s.overall_score for s in scores) / max(len(scores), 1)
    st.metric("Avg Score", f"{avg:.1f}")
with col3:
    st.metric("Top Score", f"{scores[0].overall_score:.1f} ({scores[0].grade})" if scores else "—")
with col4:
    flagged = sum(1 for s in scores if red_flag_reports.get(s.candidate.name) and red_flag_reports[s.candidate.name].total_flags > 0)
    st.metric("Flagged", f"{flagged}/{len(scores)}")

st.divider()

# ---------------------------------------------------------------------------
# Rankings table
# ---------------------------------------------------------------------------

st.subheader("Rankings")

# Build table data
rows = []
for s in scores:
    rf = red_flag_reports.get(s.candidate.name)
    rows.append({
        "Rank": s.rank,
        "Candidate": s.candidate.name,
        "Score": f"{s.overall_score:.1f}",
        "Grade": s.grade,
        "Experience": f"{s.candidate.total_experience_years:.1f} yrs",
        "Required Skills": f"{len(s.matched_required_skills)}/{len(s.matched_required_skills) + len(s.missing_required_skills)}",
        "Trust": f"{s.verification.overall_trust_score:.0%}",
        "Flags": rf.total_flags if rf else 0,
        "Risk": rf.risk_level if rf else "—",
    })

st.dataframe(
    rows,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Score": st.column_config.NumberColumn(format="%.1f"),
        "Flags": st.column_config.NumberColumn(format="%d"),
    },
)

# ---------------------------------------------------------------------------
# Candidate detail drill-down
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Candidate Detail")

names = [s.candidate.name for s in scores]
selected_name = st.selectbox("Select candidate", names)

if selected_name:
    sc = next(s for s in scores if s.candidate.name == selected_name)
    cand = sc.candidate
    rf = red_flag_reports.get(selected_name)

    # Header
    grade_class = f"grade-{sc.grade.lower().replace('+', '-plus')}"
    st.markdown(
        f'<h2>{cand.name} <span class="grade-badge {grade_class}">{sc.grade}</span></h2>',
        unsafe_allow_html=True,
    )

    # Contact
    contact_parts = []
    if cand.email:
        contact_parts.append(f"📧 {cand.email}")
    if cand.phone:
        contact_parts.append(f"📞 {cand.phone}")
    if cand.location:
        contact_parts.append(f"📍 {cand.location}")
    if contact_parts:
        st.caption(" · ".join(contact_parts))

    # Score breakdown
    tab_scores, tab_skills, tab_exp, tab_edu, tab_verify, tab_flags = st.tabs(
        ["Score Breakdown", "Skills", "Experience", "Education", "Verification", "Red Flags"]
    )

    with tab_scores:
        st.markdown(f"**Overall: {sc.overall_score:.1f}/100**")
        breakdown = sc.breakdown

        components = [
            ("Required Skills", breakdown.required_skills, 35),
            ("Preferred Skills", breakdown.preferred_skills, 15),
            ("Experience", breakdown.experience, 25),
            ("Education", breakdown.education, 10),
            ("Certifications", breakdown.certifications, 10),
            ("Semantic", breakdown.semantic_similarity, 5),
        ]

        for name, score, weight in components:
            col_label, col_bar, col_score = st.columns([3, 7, 2])
            with col_label:
                st.markdown(f"**{name}** (×{weight}%)")
            with col_bar:
                pct = min(score, 100)
                color = "#22c55e" if pct >= 70 else "#eab308" if pct >= 50 else "#ef4444"
                st.markdown(
                    f'<div style="background:#334155;border-radius:6px;height:20px;overflow:hidden">'
                    f'<div style="background:{color};height:100%;width:{pct:.0f}%"></div></div>',
                    unsafe_allow_html=True,
                )
            with col_score:
                st.markdown(f"**{score:.1f}**")

    with tab_skills:
        col_matched, col_missing = st.columns(2)
        with col_matched:
            st.markdown(f"**✅ Matched Required ({len(sc.matched_required_skills)})**")
            for s_name in sc.matched_required_skills:
                st.markdown(f"- {s_name}")
        with col_missing:
            st.markdown(f"**❌ Missing Required ({len(sc.missing_required_skills)})**")
            for s_name in sc.missing_required_skills:
                st.markdown(f"- {s_name}")

        if sc.matched_preferred_skills:
            st.divider()
            st.markdown(f"**✅ Matched Preferred ({len(sc.matched_preferred_skills)})**")
            for s_name in sc.matched_preferred_skills:
                st.markdown(f"- {s_name}")

        st.divider()
        st.markdown(f"**All Candidate Skills ({len(cand.skills)})**")
        skill_html = " ".join(
            f'<span style="display:inline-block;background:rgba(56,189,248,0.12);color:#38bdf8;'
            f'border:1px solid rgba(56,189,248,0.25);padding:0.2rem 0.5rem;margin:0.15rem;'
            f'border-radius:6px;font-size:0.8rem">{sk}</span>'
            for sk in cand.skills
        )
        st.markdown(skill_html, unsafe_allow_html=True)

    with tab_exp:
        st.markdown(f"**Total Experience: {cand.total_experience_years:.1f} years**")
        for exp in cand.experience:
            with st.container():
                st.markdown(f"**{exp.title}** at **{exp.company}**")
                date_str = exp.start_date or ""
                if exp.end_date:
                    date_str += f" → {exp.end_date}"
                if date_str:
                    st.caption(date_str)
                if exp.description:
                    st.markdown(exp.description[:300] + "..." if len(exp.description) > 300 else exp.description)
                st.divider()

    with tab_edu:
        for edu in cand.education:
            st.markdown(f"**{edu.degree}** — {edu.institution}")
            if edu.graduation_year:
                st.caption(f"Year: {edu.graduation_year}")
            st.divider()

        if cand.certifications:
            st.markdown("**Certifications**")
            for cert in cand.certifications:
                st.markdown(f"- 🏅 {cert}")

    with tab_verify:
        ver = sc.verification
        st.metric("Overall Trust Score", f"{ver.overall_trust_score:.0%}")

        # Company
        if ver.companies:
            st.markdown("**Company Verification**")
            for cv in ver.companies:
                status = "✅" if cv.verified else "❓"
                st.markdown(f"- {status} **{cv.company_name}** — {cv.method or 'N/A'}")
                if cv.notes:
                    st.caption(cv.notes)

        # Certs
        if ver.certifications:
            st.markdown("**Certification Verification**")
            for cv in ver.certifications:
                status = "✅" if cv.verified else "❓"
                st.markdown(f"- {status} **{cv.cert_name}** — {cv.method or 'N/A'}")

        # LinkedIn
        if ver.linkedin:
            lv = ver.linkedin
            status = "✅" if lv.profile_found else "❓"
            st.markdown(f"**LinkedIn:** {status}")
            if lv.url:
                st.markdown(f"URL: {lv.url}")

        # Identity
        if ver.identity:
            iv = ver.identity
            st.markdown(f"**Identity Score: {iv.overall_identity_score:.0%}**")

    with tab_flags:
        if rf:
            risk_class = f"risk-{rf.risk_level}"
            st.markdown(
                f'Risk: <span class="{risk_class}">{rf.risk_level.upper()}</span> '
                f'({rf.risk_score:.0%} score) · {rf.total_flags} flag(s)',
                unsafe_allow_html=True,
            )

            for flag in rf.flags:
                severity_icon = {"critical": "🔴", "warning": "🟡", "info": "ℹ️"}.get(flag.severity, "⚪")
                with st.container():
                    st.markdown(f"{severity_icon} **{flag.category}** — {flag.message}")
                    if flag.detail:
                        st.caption(flag.detail)
                    st.divider()

            if rf.summary:
                st.markdown("**Summary:** " + rf.summary)
        else:
            st.info("Red flag detection was not run for this candidate.")
