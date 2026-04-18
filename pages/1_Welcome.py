"""
Page 1: Welcome — Dashboard overview and quick stats.
"""
import streamlit as st

st.header("Welcome to TalentLens Pro")

st.markdown("""
<div style="padding: 2rem; background: linear-gradient(135deg, rgba(56,189,248,0.1), rgba(167,139,250,0.1));
            border: 1px solid rgba(56,189,248,0.2); border-radius: 16px; margin-bottom: 2rem;">
    <h2 style="margin:0 0 0.5rem">What's New in v3.0</h2>
    <ul style="color: #94a3b8; margin: 0;">
        <li><strong>Pipeline Management</strong> — Track candidates from upload to hire</li>
        <li><strong>Red Flag Detection</strong> — Automatically spot employment gaps, job hopping, title inflation</li>
        <li><strong>JD Quality Analyzer</strong> — Score your JD before screening</li>
        <li><strong>Role Archetypes</strong> — 12 role classifications with tailored interview guides</li>
        <li><strong>Comparison Matrix</strong> — 9-dimension weighted radar charts</li>
        <li><strong>Export Engine</strong> — PDF, DOCX, HTML, CSV, and Markdown reports</li>
        <li><strong>Executive Summaries</strong> — 1-page hiring manager reports</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# Show pipeline overview if data exists
if "scored_candidates" in st.session_state:
    scores = st.session_state["scored_candidates"]
    st.subheader(f"Current Session: {len(scores)} Candidate(s)")

    cols = st.columns(4)
    with cols[0]:
        avg = sum(s.overall_score for s in scores) / max(len(scores), 1)
        st.metric("Avg Score", f"{avg:.1f}/100")
    with cols[1]:
        top = scores[0] if scores else None
        st.metric("Top Candidate", top.candidate.name if top else "—")
    with cols[2]:
        st.metric("Top Score", f"{top.overall_score:.1f}" if top else "—")
    with cols[3]:
        avg_trust = sum(s.verification.overall_trust_score for s in scores) / max(len(scores), 1)
        st.metric("Avg Trust", f"{avg_trust:.0%}")
