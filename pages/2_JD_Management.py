"""
Page 2: JD Management — Upload, parse, analyze, and score Job Descriptions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config
from jd_analyzer import analyze_jd
from jd_quality import analyze_jd_quality
from archetypes import classify_role

st.header("📋 JD Management")

# ---------------------------------------------------------------------------
# Upload / Paste JD
# ---------------------------------------------------------------------------

tab_upload, tab_paste, tab_saved = st.tabs(["Upload File", "Paste Text", "Saved JDs"])

with tab_upload:
    uploaded = st.file_uploader(
        "Upload JD (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt"],
        help="Drag and drop or click to upload",
    )
    if uploaded:
        # Save to temp
        tmp_dir = Path(__file__).resolve().parent.parent / "data" / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / uploaded.name
        tmp_path.write_bytes(uploaded.read())
        st.session_state["_jd_upload_path"] = str(tmp_path)
        st.success(f"Uploaded: {uploaded.name}")

with tab_paste:
    jd_text = st.text_area(
        "Paste JD text here",
        height=300,
        placeholder="Paste the full job description...",
    )
    if jd_text:
        tmp_dir = Path(__file__).resolve().parent.parent / "data" / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / "pasted_jd.txt"
        tmp_path.write_text(jd_text, encoding="utf-8")
        st.session_state["_jd_upload_path"] = str(tmp_path)

with tab_saved:
    try:
        from history import get_all_jds
        saved = get_all_jds()
        if saved:
            names = [j.get("name", f"JD #{j.get('id', '?')}") for j in saved]
            selected = st.selectbox("Select a saved JD", names)
            if st.button("Load Selected JD"):
                jd_data = next(j for j in saved if j.get("name", "") == selected)
                tmp_dir = Path(__file__).resolve().parent.parent / "data" / ".tmp"
                tmp_dir.mkdir(parents=True, exist_ok=True)
                tmp_path = tmp_dir / f"saved_{selected}.txt"
                tmp_path.write_text(jd_data.get("jd_text", ""), encoding="utf-8")
                st.session_state["_jd_upload_path"] = str(tmp_path)
                st.success(f"Loaded: {selected}")
        else:
            st.info("No saved JDs yet. Parse one to save it.")
    except Exception:
        st.info("No saved JDs available.")

# ---------------------------------------------------------------------------
# Parse & Analyze
# ---------------------------------------------------------------------------

st.divider()

if st.button("🔍 Parse & Analyze JD", type="primary", use_container_width=True):
    jd_path = st.session_state.get("_jd_upload_path")
    if not jd_path:
        st.error("Upload or paste a JD first.")
    else:
        cfg = load_config()

        with st.spinner("Parsing Job Description..."):
            jd_criteria = analyze_jd(jd_path, cfg)
            st.session_state["jd_criteria"] = jd_criteria

        with st.spinner("Analyzing JD quality..."):
            quality = analyze_jd_quality(jd_criteria)
            st.session_state["jd_quality"] = quality

        with st.spinner("Classifying role archetype..."):
            archetype = classify_role(jd_criteria)
            st.session_state["jd_archetype"] = archetype

        st.success("JD parsed and analyzed!")

# ---------------------------------------------------------------------------
# Display parsed JD
# ---------------------------------------------------------------------------

if "jd_criteria" in st.session_state:
    jd = st.session_state["jd_criteria"]

    st.subheader(f"📋 {jd.title}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Role Level", jd.role_level)
    with col2:
        st.metric("Experience", f"{jd.min_experience_years}+ yrs")
    with col3:
        st.metric("Education", jd.education_level)

    # Skills
    col_req, col_pref = st.columns(2)
    with col_req:
        st.markdown(f"**Required Skills ({len(jd.required_skills)})**")
        skill_html = " ".join(
            f'<span style="display:inline-block;background:rgba(56,189,248,0.15);color:#38bdf8;'
            f'border:1px solid rgba(56,189,248,0.3);padding:0.2rem 0.6rem;margin:0.15rem;'
            f'border-radius:6px;font-size:0.85rem">{s}</span>'
            for s in jd.required_skills
        )
        st.markdown(skill_html, unsafe_allow_html=True)

    with col_pref:
        st.markdown(f"**Preferred Skills ({len(jd.preferred_skills)})**")
        skill_html = " ".join(
            f'<span style="display:inline-block;background:rgba(167,139,250,0.15);color:#a78bfa;'
            f'border:1px solid rgba(167,139,250,0.3);padding:0.2rem 0.6rem;margin:0.15rem;'
            f'border-radius:6px;font-size:0.85rem">{s}</span>'
            for s in jd.preferred_skills
        )
        st.markdown(skill_html, unsafe_allow_html=True)

    # Certifications
    if jd.certifications_required or jd.certifications_preferred:
        st.markdown("**Certifications**")
        certs = jd.certifications_required + jd.certifications_preferred
        st.write(", ".join(certs) if certs else "None specified")

    # ---------------------------------------------------------------------------
    # JD Quality Report
    # ---------------------------------------------------------------------------
    if "jd_quality" in st.session_state:
        st.divider()
        quality = st.session_state["jd_quality"]

        st.subheader("📊 JD Quality Analysis")

        # Overall score
        grade_class = f"grade-{quality.grade.lower().replace('+', '-plus')}"
        st.markdown(
            f'<span class="grade-badge {grade_class}">{quality.grade}</span> '
            f'<span style="font-size:1.5rem;font-weight:700">{quality.overall_score:.0f}/100</span> '
            f'<span style="color:#94a3b8">({quality.word_count} words, ~{quality.estimated_read_time_min} min read)</span>',
            unsafe_allow_html=True,
        )

        # Dimension bars
        for dim in quality.dimensions:
            col_label, col_bar, col_score = st.columns([2, 6, 1])
            with col_label:
                st.markdown(f"**{dim.name}**")
            with col_bar:
                color = "#22c55e" if dim.score >= 70 else "#eab308" if dim.score >= 50 else "#ef4444"
                st.markdown(
                    f'<div style="background:#334155;border-radius:6px;height:24px;overflow:hidden">'
                    f'<div style="background:{color};height:100%;width:{dim.score:.0f}%;border-radius:6px;'
                    f'transition:width 0.5s ease"></div></div>',
                    unsafe_allow_html=True,
                )
            with col_score:
                st.markdown(f"**{dim.score:.0f}**")

            # Issues/suggestions in expander
            if dim.issues or dim.suggestions:
                with st.expander(f"{dim.name} details"):
                    for issue in dim.issues:
                        st.markdown(f"- ⚠️ {issue}")
                    for sug in dim.suggestions:
                        st.markdown(f"- 💡 {sug}")

        # Red flags
        if quality.red_flags:
            st.warning("**Issues found:**")
            for flag in quality.red_flags:
                st.markdown(f"- 🚩 {flag}")

    # ---------------------------------------------------------------------------
    # Archetype
    # ---------------------------------------------------------------------------
    if "jd_archetype" in st.session_state:
        st.divider()
        arch = st.session_state["jd_archetype"]

        st.subheader("🎯 Role Archetype")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Primary:** {arch.primary.archetype} ({arch.primary.confidence:.0%} confidence)")
            st.caption(arch.primary.description)
            st.markdown("**Key Skills:** " + ", ".join(arch.primary.key_skills))
        with col2:
            if arch.secondary:
                st.markdown(f"**Secondary:** {arch.secondary.archetype} ({arch.secondary.confidence:.0%} confidence)")
                st.caption(arch.secondary.description)
            st.markdown(f"**Complexity:** {arch.role_complexity.replace('_', ' ').title()}")
            st.markdown(f"**Suggested Panel:** {', '.join(arch.suggested_panel)}")

        with st.expander("Interview Focus Areas"):
            for focus in arch.primary.interview_focus:
                st.markdown(f"- {focus}")
