"""
TalentLens Pro — Streamlit Multipage Dashboard Entry Point.

Launch with:
    streamlit run app.py --server.port 8503
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------------------
# Page config (MUST be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TalentLens Pro",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
/* Dark theme overrides for professional look */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

.stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
}

[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #38bdf8;
}

/* Card-like containers */
.stMetric {
    background: rgba(30, 41, 59, 0.5);
    border: 1px solid rgba(51, 65, 85, 0.5);
    border-radius: 12px;
    padding: 1rem;
}

/* Grade badges */
.grade-badge {
    display: inline-block;
    padding: 0.25rem 0.75rem;
    border-radius: 8px;
    font-weight: 700;
    font-size: 1.1rem;
    color: white;
}
.grade-a-plus, .grade-a { background: #22c55e; }
.grade-b-plus, .grade-b { background: #38bdf8; }
.grade-c { background: #eab308; }
.grade-d { background: #f97316; }
.grade-f { background: #ef4444; }

/* Risk badges */
.risk-high { color: #ef4444; font-weight: 700; }
.risk-medium { color: #eab308; font-weight: 700; }
.risk-low { color: #22c55e; font-weight: 700; }
.risk-clean { color: #38bdf8; font-weight: 700; }

/* Subtle animations */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.animate-in {
    animation: fadeIn 0.3s ease-out;
}

/* Pipeline stage colors */
.stage-uploaded { color: #94a3b8; }
.stage-parsed { color: #64748b; }
.stage-scored { color: #38bdf8; }
.stage-shortlisted { color: #a78bfa; }
.stage-interview { color: #f59e0b; }
.stage-interviewed { color: #fb923c; }
.stage-offer { color: #22c55e; }
.stage-hired { color: #10b981; font-weight: 700; }
.stage-rejected { color: #ef4444; }
.stage-withdrawn { color: #6b7280; }

/* Button overrides */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);
}

/* Hide Streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

# Define pages
pages = {
    "Welcome": "pages/1_Welcome.py",
    "JD Management": "pages/2_JD_Management.py",
    "Screening": "pages/3_Screening.py",
    "Results & Rankings": "pages/4_Results.py",
    "Candidate Pipeline": "pages/5_Pipeline.py",
    "Comparison Matrix": "pages/6_Comparison.py",
    "Agent Panel": "pages/7_Agent_Panel.py",
    "Analytics": "pages/8_Analytics.py",
    "Export Center": "pages/9_Export.py",
    "History": "pages/10_History.py",
}

# Sidebar
with st.sidebar:
    st.markdown("# 🔍 TalentLens Pro")
    st.markdown("*AI-Powered Resume Screening*")
    st.divider()

    # Session info
    if "jd_criteria" in st.session_state:
        jd = st.session_state["jd_criteria"]
        st.success(f"📋 JD: {jd.title}")
        if "scored_candidates" in st.session_state:
            n = len(st.session_state["scored_candidates"])
            st.info(f"👥 {n} candidate(s) scored")
    else:
        st.warning("No JD loaded — start with JD Management")

    st.divider()
    st.markdown("""
    <div style="font-size:0.75rem; color:#64748b; text-align:center;">
        TalentLens Pro v3.0<br>
        11 AI Agents · 164+ Skills<br>
        9-Layer Verification
    </div>
    """, unsafe_allow_html=True)


# Main content — show Welcome if no page navigation
st.markdown("""
<div style="text-align: center; padding: 3rem 0;">
    <h1 style="font-size: 3rem; font-weight: 800; background: linear-gradient(135deg, #38bdf8, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
        TalentLens Pro
    </h1>
    <p style="font-size: 1.3rem; color: #94a3b8; max-width: 600px; margin: 1rem auto;">
        AI-powered resume screening with multi-agent evaluation,
        9-layer verification, and intelligent pipeline management.
    </p>
</div>
""", unsafe_allow_html=True)

# Quick stats
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("AI Agents", "11", help="Specialist evaluation agents")
with col2:
    st.metric("Skills Taxonomy", "164+", help="Recognized technical skills")
with col3:
    st.metric("Verification Layers", "9", help="Company verification depth")
with col4:
    st.metric("Export Formats", "5", help="PDF, DOCX, HTML, CSV, Markdown")

st.divider()

# Quick start guide
st.markdown("## Quick Start")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    ### 1️⃣ Load a JD
    Upload or paste a Job Description.
    The system will parse skills, experience,
    and education requirements automatically.

    👉 **Go to JD Management**
    """)

with col2:
    st.markdown("""
    ### 2️⃣ Screen Resumes
    Upload one or more resumes.
    Each gets scored, verified, and analyzed
    by 11 specialist AI agents.

    👉 **Go to Screening**
    """)

with col3:
    st.markdown("""
    ### 3️⃣ Compare & Decide
    View rankings, comparison radar charts,
    red flag reports, and export professional
    reports in any format.

    👉 **Go to Results**
    """)
