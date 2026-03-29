"""
dashboard_v3.py  –  Multi-Page Resume Screening Dashboard (Streamlit).

Pages:
  1. Welcome        –  Landing screen, animated hero, quick stats
  2. JD Management  –  Create / save / select / edit JDs, AI-assisted creation
  3. Screening      –  Step-by-step pipeline with progress
  4. Results        –  Candidate cards, charts, verification
  5. Agent Panel    –  11-agent grid, radar, discussion
  6. History        –  Past screenings, search
  7. Analytics      –  Aggregate stats, trends
  8. Interview Prep –  Generated questionnaires + DOCX export

Run:  streamlit run dashboard_v3.py
"""
from __future__ import annotations

import json
import pickle
import sys
import time
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
from agents import evaluate_candidate, ConsensusResult, AGENT_CATALOGUE
from history import (
    save_session, get_all_sessions, get_candidates_for_session,
    get_all_candidates, get_stats_summary, get_candidate_history,
    get_sessions_by_month, get_sessions_by_year,
    save_jd, get_all_jds, get_jd, update_jd, delete_jd, increment_jd_use_count,
)
from interview_gen import generate_questionnaire, export_questionnaire_docx
from models import CandidateScore, JDCriteria
from heuristics import extract_skills, extract_experience_range, extract_education_level, \
    extract_role_level, extract_jd_title, infer_industry

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TalentLens",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — glassmorphism, animations, refined typography
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

    /* ── Hero header ── */
    .hero {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
        padding: 2rem 2.5rem; border-radius: 16px; margin-bottom: 1.5rem;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        position: relative; overflow: hidden;
    }
    .hero::before {
        content: ''; position: absolute; top: -50%; right: -20%; width: 400px; height: 400px;
        background: radial-gradient(circle, rgba(56,189,248,0.12) 0%, transparent 70%);
        pointer-events: none;
    }
    .hero h1 { color: #f1f5f9; font-size: 2rem; font-weight: 800; margin: 0; letter-spacing: -0.02em; }
    .hero .subtitle { color: #94a3b8; margin: 0.4rem 0 0 0; font-size: 0.95rem; font-weight: 400; }
    .hero .badge {
        display: inline-block; background: rgba(56,189,248,0.15); color: #38bdf8;
        padding: 0.2rem 0.7rem; border-radius: 20px; font-size: 0.75rem;
        font-weight: 600; letter-spacing: 0.03em; margin-top: 0.5rem;
        border: 1px solid rgba(56,189,248,0.25);
    }

    /* ── Glass metric cards ── */
    .glass-card {
        background: rgba(30, 41, 59, 0.6); backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255,255,255,0.08); border-radius: 16px;
        padding: 1.5rem; text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .glass-card:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(0,0,0,0.3); }
    .glass-card .value {
        font-size: 2.4rem; font-weight: 800; letter-spacing: -0.02em;
        background: linear-gradient(135deg, #38bdf8, #818cf8);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .glass-card .label {
        font-size: 0.78rem; color: #64748b; text-transform: uppercase;
        letter-spacing: 0.08em; margin-top: 0.3rem; font-weight: 600;
    }
    .glass-card .sublabel { font-size: 0.7rem; color: #475569; margin-top: 0.15rem; }

    /* ── Feature cards (Welcome) ── */
    .feature-card {
        background: rgba(30,41,59,0.5); backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.06); border-radius: 14px;
        padding: 1.5rem; text-align: center; min-height: 180px;
        transition: transform 0.2s ease, border-color 0.3s ease;
    }
    .feature-card:hover { transform: translateY(-3px); border-color: rgba(56,189,248,0.3); }
    .feature-card .icon { font-size: 2.2rem; margin-bottom: 0.5rem; }
    .feature-card h4 { color: #e2e8f0; font-size: 1rem; margin: 0.4rem 0; font-weight: 700; }
    .feature-card p { color: #94a3b8; font-size: 0.85rem; line-height: 1.5; margin: 0; }

    /* ── Agent cards ── */
    .agent-tile {
        background: rgba(30,41,59,0.5); border-radius: 12px;
        padding: 1rem 1.2rem; border-left: 4px solid #3b82f6;
        transition: transform 0.15s ease; min-height: 80px;
    }
    .agent-tile:hover { transform: translateX(3px); }
    .agent-tile .aname { font-weight: 700; color: #e2e8f0; font-size: 0.9rem; }
    .agent-tile .adesc { color: #64748b; font-size: 0.78rem; margin-top: 0.2rem; }
    .agent-tile .aweight {
        display: inline-block; background: rgba(56,189,248,0.15); color: #38bdf8;
        padding: 0.1rem 0.5rem; border-radius: 10px; font-size: 0.7rem;
        font-weight: 700; margin-top: 0.3rem;
    }
    .agent-tile.green { border-left-color: #10b981; }
    .agent-tile.blue { border-left-color: #3b82f6; }
    .agent-tile.yellow { border-left-color: #f59e0b; }
    .agent-tile.red { border-left-color: #ef4444; }
    .agent-tile.purple { border-left-color: #8b5cf6; }
    .agent-tile.cyan { border-left-color: #06b6d4; }

    /* ── Section headers ── */
    .sec-header {
        border-left: 4px solid #3b82f6; padding-left: 14px;
        margin: 2rem 0 1.2rem 0; font-size: 1.15rem; font-weight: 700;
        color: #e2e8f0; letter-spacing: -0.01em;
    }
    .sec-header.green { border-left-color: #10b981; }
    .sec-header.purple { border-left-color: #8b5cf6; }
    .sec-header.yellow { border-left-color: #f59e0b; }

    /* ── Candidate rank badges ── */
    .rank-badge {
        display: inline-flex; align-items: center; gap: 0.4rem;
        padding: 0.3rem 0.8rem; border-radius: 8px; font-weight: 700;
        font-size: 0.85rem;
    }
    .rank-badge.gold { background: rgba(245,158,11,0.15); color: #f59e0b; }
    .rank-badge.silver { background: rgba(148,163,184,0.15); color: #94a3b8; }
    .rank-badge.bronze { background: rgba(234,88,12,0.15); color: #ea580c; }
    .rank-badge.default { background: rgba(100,116,139,0.1); color: #64748b; }

    /* ── Grade pills ── */
    .grade-pill {
        display: inline-block; padding: 0.15rem 0.6rem; border-radius: 6px;
        font-weight: 800; font-size: 0.8rem; letter-spacing: 0.03em;
    }
    .grade-pill.a-plus, .grade-pill.a { background: rgba(16,185,129,0.15); color: #10b981; }
    .grade-pill.b-plus, .grade-pill.b { background: rgba(59,130,246,0.15); color: #3b82f6; }
    .grade-pill.c { background: rgba(245,158,11,0.15); color: #f59e0b; }
    .grade-pill.d { background: rgba(249,115,22,0.15); color: #f97316; }
    .grade-pill.f { background: rgba(239,68,68,0.15); color: #ef4444; }

    /* ── Step indicator ── */
    .step-row { display: flex; justify-content: center; gap: 0; margin: 1.5rem 0; }
    .step-item {
        display: flex; align-items: center; gap: 0.5rem;
        padding: 0.6rem 1.2rem; font-size: 0.85rem; font-weight: 600;
        color: #475569; position: relative;
    }
    .step-item.active { color: #38bdf8; }
    .step-item.done { color: #10b981; }
    .step-num {
        width: 28px; height: 28px; border-radius: 50%; display: inline-flex;
        align-items: center; justify-content: center; font-size: 0.75rem;
        font-weight: 800; border: 2px solid #334155;
    }
    .step-item.active .step-num { border-color: #38bdf8; background: rgba(56,189,248,0.15); color: #38bdf8; }
    .step-item.done .step-num { border-color: #10b981; background: rgba(16,185,129,0.15); color: #10b981; }
    .step-connector { width: 40px; height: 2px; background: #334155; align-self: center; }
    .step-connector.done { background: #10b981; }

    /* ── Discussion bubbles ── */
    .disc-bubble {
        background: rgba(30,41,59,0.6); border-radius: 10px;
        padding: 0.6rem 1rem; margin: 0.4rem 0;
        border-left: 3px solid #475569; font-size: 0.88rem; color: #cbd5e1;
    }
    .disc-bubble .agent { font-weight: 700; color: #38bdf8; }
    .disc-bubble .round { color: #475569; font-size: 0.75rem; font-weight: 600; }

    /* ── Pipeline progress ── */
    .pipeline-status {
        background: rgba(30,41,59,0.7); border-radius: 12px;
        padding: 1rem 1.5rem; border: 1px solid rgba(255,255,255,0.06);
        margin: 0.5rem 0;
    }
    .pipeline-status .step { display: flex; align-items: center; gap: 0.6rem; padding: 0.3rem 0; }
    .pipeline-status .step .icon { font-size: 1.1rem; }
    .pipeline-status .step .text { color: #94a3b8; font-size: 0.85rem; }
    .pipeline-status .step.active .text { color: #38bdf8; font-weight: 600; }
    .pipeline-status .step.done .text { color: #10b981; }

    /* ── Empty state ── */
    .empty-state {
        text-align: center; padding: 3rem 2rem;
        background: rgba(30,41,59,0.3); border-radius: 16px;
        border: 1px dashed rgba(100,116,139,0.3);
    }
    .empty-state .icon { font-size: 3rem; margin-bottom: 0.5rem; }
    .empty-state h3 { color: #94a3b8; font-weight: 600; margin: 0.5rem 0; }
    .empty-state p { color: #64748b; font-size: 0.9rem; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0c0e1a 0%, #131629 40%, #1a1d35 100%);
    }
    [data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    [data-testid="stSidebar"] .stRadio label { padding: 0.4rem 0; }

    /* ── Data tables ── */
    .stDataFrame thead th {
        background: rgba(30,41,59,0.8) !important; color: #e2e8f0 !important;
        font-weight: 700 !important; font-size: 0.82rem !important;
    }

    /* ── Global tweaks ── */
    .stExpander { border: 1px solid rgba(255,255,255,0.06) !important; border-radius: 12px !important; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; }
    div[data-testid="stMetric"] label { font-size: 0.78rem !important; color: #64748b !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 1.6rem !important; font-weight: 800 !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        border: none !important; font-weight: 700 !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #2563eb, #7c3aed) !important;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
_SESSION_FILE = Path(__file__).parent / "data" / ".session_state.pkl"
_UPLOAD_DIR = Path(__file__).parent / "data" / ".uploads"

_DEFAULTS = {
    "jd_criteria": None,
    "scores": [],
    "agent_results": {},
    "questionnaires": {},
    "jd_text": "",
    "last_session_id": None,
    "selected_jd_id": None,
    "current_page": "Welcome",
    "pipeline_stage": None,
    # ── New: Upload persistence ──
    "uploaded_resume_data": {},       # {filename: bytes}
    "uploaded_jd_source_text": "",    # JD text that was screened
    "uploaded_jd_name": "",           # JD name/label
    # ── New: Pipeline state ──
    "pipeline_completed": False,
    "pipeline_timestamp": None,
    "pipeline_candidate_count": 0,
    # ── New: Navigation ──
    "auto_navigate_to": None,
    # ── New: Session recovery ──
    "_state_restored": False,
}

for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Disk persistence — survives browser refresh + server restart
# ---------------------------------------------------------------------------
_PERSIST_KEYS = [
    "jd_criteria", "scores", "agent_results", "questionnaires",
    "jd_text", "last_session_id", "selected_jd_id",
    "uploaded_jd_source_text", "uploaded_jd_name",
    "pipeline_completed", "pipeline_timestamp", "pipeline_candidate_count",
    "uploaded_resume_data",
]


def _save_state_to_disk():
    """Pickle critical session state to disk for persistence."""
    try:
        _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        for key in _PERSIST_KEYS:
            if key in st.session_state:
                data[key] = st.session_state[key]
        with open(_SESSION_FILE, "wb") as f:
            pickle.dump(data, f)
    except Exception:
        pass  # Non-critical — don't break the app


def _restore_state_from_disk():
    """Restore session state from disk if available."""
    if st.session_state.get("_state_restored"):
        return False
    st.session_state._state_restored = True
    if not _SESSION_FILE.exists():
        return False
    try:
        with open(_SESSION_FILE, "rb") as f:
            data = pickle.load(f)  # noqa: S301  — trusted local file only
        if not isinstance(data, dict):
            return False
        has_data = bool(data.get("scores") or data.get("pipeline_completed"))
        if has_data:
            for key, val in data.items():
                if key in _PERSIST_KEYS:
                    st.session_state[key] = val
        return has_data
    except Exception:
        return False


def _clear_persisted_state():
    """Clear persisted state from disk and reset session."""
    try:
        _SESSION_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    for key, default in _DEFAULTS.items():
        if key != "_state_restored":
            st.session_state[key] = default


# Auto-restore on first load
_had_saved_session = _restore_state_from_disk()


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


def _save_upload_from_bytes(name: str, data: bytes) -> Path:
    """Save cached file bytes to disk, return path."""
    tmp = Path(__file__).parent / "data" / ".tmp"
    tmp.mkdir(exist_ok=True)
    p = tmp / name
    p.write_bytes(data)
    return p


def _cache_resume_uploads(resume_files):
    """Cache uploaded resume file bytes to session_state for persistence."""
    if resume_files:
        cached = {}
        for f in resume_files:
            cached[f.name] = f.getvalue()
            f.seek(0)
        st.session_state.uploaded_resume_data = cached


def _grade_color(grade: str) -> str:
    return {"A+": "#10b981", "A": "#10b981", "B+": "#3b82f6", "B": "#3b82f6",
            "C": "#f59e0b", "D": "#f97316", "F": "#ef4444"}.get(grade, "#94a3b8")


def _grade_css(grade: str) -> str:
    return {"A+": "a-plus", "A": "a", "B+": "b-plus", "B": "b",
            "C": "c", "D": "d", "F": "f"}.get(grade, "")


def _rec_color(rec: str) -> str:
    if "Strong" in rec: return "#10b981"
    if rec == "Hire": return "#3b82f6"
    if "Lean" in rec: return "#f59e0b"
    return "#ef4444"


def _agent_icon(name: str) -> str:
    return {
        "Application Architect": "🏗️",
        "Product Owner": "📦",
        "Security Architect": "🔒",
        "QA Architect": "🧪",
        "SRE Engineer": "⚙️",
        "Cloud Solutions Architect": "☁️",
        "AWS Migration Engineer": "🔄",
        "Cloud Operations Engineer": "📡",
        "AWS Platform Engineer": "🛠️",
        "HR Manager": "👥",
        "Recruiting Engineer": "🎯",
    }.get(name, "🤖")


_AGENT_COLORS = {
    "Application Architect": "blue",
    "Product Owner": "purple",
    "Security Architect": "red",
    "QA Architect": "yellow",
    "SRE Engineer": "cyan",
    "Cloud Solutions Architect": "blue",
    "AWS Migration Engineer": "green",
    "Cloud Operations Engineer": "cyan",
    "AWS Platform Engineer": "purple",
    "HR Manager": "green",
    "Recruiting Engineer": "yellow",
}


def _hero(title: str, subtitle: str, badge: str = ""):
    badge_html = f'<div class="badge">{badge}</div>' if badge else ""
    st.markdown(f"""
    <div class="hero">
        <h1>{title}</h1>
        <p class="subtitle">{subtitle}</p>
        {badge_html}
    </div>
    """, unsafe_allow_html=True)


def _glass_metric(value, label, sublabel=""):
    sub_html = f'<div class="sublabel">{sublabel}</div>' if sublabel else ""
    return f'<div class="glass-card"><div class="value">{value}</div><div class="label">{label}</div>{sub_html}</div>'


def _empty_state(icon: str, title: str, desc: str):
    st.markdown(f"""
    <div class="empty-state">
        <div class="icon">{icon}</div>
        <h3>{title}</h3>
        <p>{desc}</p>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
PAGES = ["🏠 Welcome", "📄 JD Management", "🔍 Screening", "📊 Results",
         "🤖 Agent Panel", "📅 History", "📈 Analytics", "❓ Interview Prep"]

# Handle auto-navigation (e.g., after pipeline completion)
_nav_target = st.session_state.get("auto_navigate_to")
_default_page_idx = 0
if _nav_target and _nav_target in PAGES:
    _default_page_idx = PAGES.index(_nav_target)
    st.session_state.auto_navigate_to = None

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 1.2rem 0 0.8rem 0;">
        <div style="font-size:2.5rem; margin-bottom:0.3rem;">🔍</div>
        <div style="font-size:1.3rem; font-weight:800; letter-spacing:-0.02em;
                    background:linear-gradient(135deg,#38bdf8,#818cf8);
                    -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
            TalentLens
        </div>
        <div style="color:#475569; font-size:0.72rem; font-weight:600;
                    letter-spacing:0.1em; text-transform:uppercase; margin-top:0.2rem;">
            See beyond the resume
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("---")
    selected_page = st.radio("Navigate", PAGES, index=_default_page_idx, label_visibility="collapsed")
    st.markdown("---")

    # Pipeline status in sidebar
    scores = st.session_state.scores
    agent_results = st.session_state.agent_results
    questionnaires = st.session_state.questionnaires

    if scores:
        _ts = st.session_state.get("pipeline_timestamp", "")
        _ts_label = f" · {_ts}" if _ts else ""
        st.markdown(f"""
        <div class="pipeline-status">
            <div style="font-size:0.72rem; color:#475569; font-weight:600; letter-spacing:0.05em;
                        text-transform:uppercase; margin-bottom:0.5rem;">Active Session{_ts_label}</div>
            <div class="step done"><span class="icon">✅</span><span class="text">{len(scores)} candidates scored</span></div>
            <div class="step {'done' if agent_results else ''}"><span class="icon">{'✅' if agent_results else '⬜'}</span><span class="text">{len(agent_results)} agent evals</span></div>
            <div class="step {'done' if questionnaires else ''}"><span class="icon">{'✅' if questionnaires else '⬜'}</span><span class="text">{len(questionnaires)} questionnaires</span></div>
        </div>
        """, unsafe_allow_html=True)

        # Clear session button
        if st.button("🗑️ Clear Current Session", use_container_width=True):
            _clear_persisted_state()
            st.rerun()
    elif _had_saved_session and st.session_state.pipeline_completed:
        st.success("♻️ Previous session restored!")
    else:
        st.caption("No active screening session")

    # Quick stats
    st.markdown("---")
    try:
        _stats = get_stats_summary()
        st.caption(f"📊 {_stats['total_sessions']} sessions · {_stats['total_candidates']} candidates")
    except Exception:
        st.caption("📊 No history yet")

    st.markdown("---")
    st.markdown("""
    <div style="text-align:center; padding:0.5rem 0;">
        <span style="color:#334155; font-size:0.7rem;">TalentLens v3.0 · 11 Agents · Heuristic Mode</span>
    </div>
    """, unsafe_allow_html=True)


# =====================================================================
# PAGE: WELCOME
# =====================================================================
if selected_page == "🏠 Welcome":
    _hero("🔍 TalentLens",
          "See beyond the resume — Multi-Agent Evaluation · Skills Matching · Verification · Interview Prep",
          "11 SPECIALIST AGENTS")

    # Session recovery banner
    if _had_saved_session and st.session_state.pipeline_completed:
        _cnt = st.session_state.pipeline_candidate_count or len(st.session_state.scores)
        st.info(f"♻️ **Previous session restored** — {_cnt} candidates screened. Navigate to **📊 Results** to review.")

    # Quick stats
    try:
        stats = get_stats_summary()
    except Exception:
        stats = {"total_sessions": 0, "total_candidates": 0, "avg_score": 0,
                 "top_candidate": None, "grade_distribution": {}, "monthly_trend": []}

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(_glass_metric(stats["total_sessions"], "Sessions", "screening runs"), unsafe_allow_html=True)
    with c2:
        st.markdown(_glass_metric(stats["total_candidates"], "Candidates", "resumes analyzed"), unsafe_allow_html=True)
    with c3:
        st.markdown(_glass_metric(f'{stats["avg_score"]:.1f}', "Avg Score", "out of 100"), unsafe_allow_html=True)
    with c4:
        try:
            jd_count = len(get_all_jds())
        except Exception:
            jd_count = 0
        st.markdown(_glass_metric(jd_count, "Saved JDs", "job descriptions"), unsafe_allow_html=True)

    st.markdown("")

    # How it works — feature cards
    st.markdown('<div class="sec-header">🚀 How It Works</div>', unsafe_allow_html=True)
    w1, w2, w3, w4 = st.columns(4)
    features = [
        ("📄", "Manage JDs", "Create, save, and manage job descriptions. Use the AI builder to generate JDs from scratch."),
        ("📤", "Upload Resumes", "Upload candidate resumes in PDF or DOCX format. Batch process multiple files at once."),
        ("🤖", "AI Screening", "11 specialist agents evaluate each candidate with skills matching, verification & scoring."),
        ("📝", "Interview Prep", "Auto-generate targeted questionnaires. Download as DOCX for your interview panel."),
    ]
    for col, (icon, title, desc) in zip([w1, w2, w3, w4], features):
        with col:
            st.markdown(f"""
            <div class="feature-card">
                <div class="icon">{icon}</div>
                <h4>{title}</h4>
                <p>{desc}</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("")

    # Agent panel overview
    st.markdown('<div class="sec-header purple">🤖 11 Specialist Agents</div>', unsafe_allow_html=True)
    agents_info = [
        ("🏗️", "Application Architect", "System design & scalability", "8%", "blue"),
        ("📦", "Product Owner", "Delivery & domain fit", "6%", "purple"),
        ("🔒", "Security Architect", "Security & compliance", "10%", "red"),
        ("🧪", "QA Architect", "Testing & code quality", "6%", "yellow"),
        ("⚙️", "SRE Engineer", "Ops & observability", "8%", "cyan"),
        ("☁️", "Cloud Solutions Architect", "AWS architecture & design", "14%", "blue"),
        ("🔄", "AWS Migration Engineer", "Migration strategy & 6Rs", "12%", "green"),
        ("📡", "Cloud Ops Engineer", "Day-2 ops & cost optimization", "10%", "cyan"),
        ("🛠️", "AWS Platform Engineer", "IaC & container orchestration", "8%", "purple"),
        ("👥", "HR Manager", "Culture fit & career progression", "10%", "green"),
        ("🎯", "Recruiting Engineer", "Role alignment & market fit", "8%", "yellow"),
    ]

    # 3 rows of agents
    for row_start in range(0, len(agents_info), 4):
        row = agents_info[row_start:row_start + 4]
        cols = st.columns(len(row))
        for col, (icon, name, desc, weight, color) in zip(cols, row):
            with col:
                st.markdown(f"""
                <div class="agent-tile {color}">
                    <div class="aname">{icon} {name}</div>
                    <div class="adesc">{desc}</div>
                    <span class="aweight">{weight}</span>
                </div>
                """, unsafe_allow_html=True)

    # Quick navigation
    st.markdown("")
    st.markdown('<div class="sec-header green">⚡ Quick Start</div>', unsafe_allow_html=True)
    qc1, qc2, qc3 = st.columns(3)
    with qc1:
        if st.button("📄 Create a JD", use_container_width=True):
            st.session_state.current_page = "📄 JD Management"
            st.rerun()
    with qc2:
        if st.button("🔍 Start Screening", type="primary", use_container_width=True):
            st.session_state.current_page = "🔍 Screening"
            st.rerun()
    with qc3:
        if st.button("📅 View History", use_container_width=True):
            st.session_state.current_page = "📅 History"
            st.rerun()


# =====================================================================
# PAGE: JD MANAGEMENT
# =====================================================================
elif selected_page == "📄 JD Management":
    _hero("📄 Job Description Management",
          "Create, save, edit, and manage job descriptions",
          "AI-ASSISTED BUILDER")

    jd_tab_create, jd_tab_saved, jd_tab_ai = st.tabs([
        "✏️ Create / Upload", "📚 Saved JDs", "🤖 AI Builder"
    ])

    # --- Create / Upload ---
    with jd_tab_create:
        st.markdown('<div class="sec-header">✏️ Create or Upload a Job Description</div>', unsafe_allow_html=True)

        jc1, jc2 = st.columns([2, 1])
        with jc1:
            jd_name = st.text_input("JD Name *", placeholder="e.g. Senior DevOps Engineer - Team Alpha")
        with jc2:
            jd_tags_str = st.text_input("Tags (comma-separated)", placeholder="devops, senior, remote")

        create_method = st.radio("How to add JD:", ["Paste/Type Text", "Upload File"], horizontal=True)

        jd_text_input = ""
        if create_method == "Paste/Type Text":
            jd_text_input = st.text_area("Job Description Text:", height=300,
                                          placeholder="Paste or type the full job description here...")
        else:
            jd_upload = st.file_uploader("Upload JD File", type=["pdf", "docx", "doc", "txt"],
                                          key="jd_mgmt_upload")
            if jd_upload:
                p = _save_upload(jd_upload)
                try:
                    from jd_analyzer import _extract_text
                    jd_text_input = _extract_text(p)
                    st.text_area("Extracted Text:", value=jd_text_input, height=200,
                                 key="jd_extracted_preview", disabled=True)
                except Exception as e:
                    st.error(f"Failed to extract text: {e}")

        col_save, col_preview = st.columns(2)
        with col_save:
            if st.button("💾 Save JD", type="primary", use_container_width=True):
                if not jd_name.strip():
                    st.error("Please provide a JD name.")
                elif not jd_text_input.strip():
                    st.error("Please provide JD text or upload a file.")
                else:
                    tags = [t.strip() for t in jd_tags_str.split(",") if t.strip()] if jd_tags_str else []
                    try:
                        cfg = load_config()
                        jd_criteria = analyze_jd(jd_text_input, cfg)
                        from history import _safe_asdict
                        jd_data = _safe_asdict(jd_criteria)
                    except Exception:
                        jd_data = {}
                    jd_id = save_jd(jd_name.strip(), jd_text_input.strip(), jd_data, tags)
                    st.success(f"✅ JD '{jd_name}' saved!")
                    st.rerun()

        with col_preview:
            if jd_text_input.strip() and st.button("👁️ Preview Analysis", use_container_width=True):
                with st.spinner("Analyzing…"):
                    try:
                        cfg = load_config()
                        preview_jd = analyze_jd(jd_text_input, cfg)
                        st.write(f"**Title:** {preview_jd.title}")
                        st.write(f"**Level:** {preview_jd.role_level} | **Industry:** {preview_jd.industry}")
                        st.write(f"**Min Exp:** {preview_jd.min_experience_years}y | **Education:** {preview_jd.education_level}")
                        st.write(f"**Required:** {', '.join(preview_jd.required_skills[:8])}")
                        st.write(f"**Preferred:** {', '.join(preview_jd.preferred_skills[:8])}")
                    except Exception as e:
                        st.error(f"Analysis failed: {e}")

    # --- Saved JDs ---
    with jd_tab_saved:
        st.markdown('<div class="sec-header">📚 Saved Job Descriptions</div>', unsafe_allow_html=True)

        try:
            saved_jds = get_all_jds()
        except Exception:
            saved_jds = []

        if not saved_jds:
            _empty_state("📄", "No Saved JDs", "Create a JD in the 'Create / Upload' tab to get started.")
        else:
            st.markdown(f"**{len(saved_jds)} saved job description(s)**")

            jd_rows = []
            for jd_item in saved_jds:
                tags = jd_item.get("tags", [])
                tag_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
                jd_rows.append({
                    "ID": jd_item["id"],
                    "Name": jd_item["name"],
                    "Created": jd_item["created_at"][:16],
                    "Tags": tag_str,
                    "Used": jd_item.get("use_count", 0),
                })
            st.dataframe(pd.DataFrame(jd_rows), use_container_width=True, hide_index=True)

            selected_jd_id = st.selectbox(
                "Select JD to view/edit:",
                options=[j["id"] for j in saved_jds],
                format_func=lambda x: f"{x} — {next((j['name'] for j in saved_jds if j['id']==x), '')}",
                key="jd_detail_select",
            )

            if selected_jd_id:
                jd_detail = get_jd(selected_jd_id)
                if jd_detail:
                    st.markdown(f"### {jd_detail['name']}")
                    st.caption(f"Created: {jd_detail['created_at'][:16]} · Used: {jd_detail.get('use_count', 0)} times")

                    new_name = st.text_input("Name:", value=jd_detail["name"], key="edit_jd_name")
                    new_text = st.text_area("JD Text:", value=jd_detail["jd_text"], height=200, key="edit_jd_text")
                    tags_val = jd_detail.get("tags", [])
                    new_tags_str = st.text_input("Tags:", value=", ".join(tags_val) if isinstance(tags_val, list) else "",
                                                  key="edit_jd_tags")

                    ec1, ec2, ec3 = st.columns(3)
                    with ec1:
                        if st.button("💾 Update", use_container_width=True):
                            new_tags = [t.strip() for t in new_tags_str.split(",") if t.strip()]
                            update_jd(selected_jd_id, name=new_name, jd_text=new_text, tags=new_tags)
                            st.success("✅ Updated!")
                            st.rerun()
                    with ec2:
                        if st.button("📋 Use for Screening", use_container_width=True, type="primary"):
                            st.session_state.selected_jd_id = selected_jd_id
                            st.session_state.jd_text = jd_detail["jd_text"]
                            st.success("JD selected! Navigate to Screening page.")
                    with ec3:
                        if st.button("🗑️ Delete", use_container_width=True):
                            delete_jd(selected_jd_id)
                            st.success("Deleted.")
                            st.rerun()

                    jd_data_parsed = jd_detail.get("jd_data", {})
                    if isinstance(jd_data_parsed, dict) and jd_data_parsed:
                        with st.expander("📊 Parsed Analysis"):
                            st.write(f"**Title:** {jd_data_parsed.get('title', 'N/A')}")
                            st.write(f"**Role Level:** {jd_data_parsed.get('role_level', 'N/A')}")
                            st.write(f"**Required Skills:** {', '.join(jd_data_parsed.get('required_skills', []))}")
                            st.write(f"**Preferred Skills:** {', '.join(jd_data_parsed.get('preferred_skills', []))}")

    # --- AI-Assisted Creation ---
    with jd_tab_ai:
        st.markdown('<div class="sec-header">🤖 AI-Assisted JD Builder</div>', unsafe_allow_html=True)
        st.caption("Fill in the basics and we'll generate a complete job description.")

        ai_c1, ai_c2 = st.columns(2)
        with ai_c1:
            ai_title = st.text_input("Job Title *", placeholder="e.g. Senior Cloud Engineer")
            ai_level = st.selectbox("Role Level", ["Junior", "Mid", "Senior", "Lead", "Principal", "Executive"])
            ai_industry = st.text_input("Industry", placeholder="e.g. FinTech, Healthcare")
            ai_location = st.text_input("Location", placeholder="e.g. Remote, Bangalore")
        with ai_c2:
            ai_exp_min = st.number_input("Min Experience (years)", min_value=0, max_value=30, value=3)
            ai_exp_max = st.number_input("Max Experience (years, 0=any)", min_value=0, max_value=30, value=0)
            ai_education = st.selectbox("Education Level", ["Any", "Bachelor", "Master", "PhD"])
            ai_team = st.text_input("Team/Department", placeholder="e.g. Platform Engineering")

        ai_must_skills = st.text_input("Must-Have Skills", placeholder="e.g. AWS, Terraform, Kubernetes, Python")
        ai_nice_skills = st.text_input("Nice-to-Have Skills", placeholder="e.g. GCP, Ansible, Prometheus")
        ai_certs = st.text_input("Preferred Certifications", placeholder="e.g. AWS SAA, CKA")
        ai_extra = st.text_area("Additional Notes", height=80,
                                 placeholder="e.g. On-call rotation required...")

        if st.button("🪄 Generate JD", type="primary", use_container_width=True):
            if not ai_title.strip():
                st.error("Please provide at least a job title.")
            else:
                must = [s.strip() for s in ai_must_skills.split(",") if s.strip()]
                nice = [s.strip() for s in ai_nice_skills.split(",") if s.strip()]
                certs = [s.strip() for s in ai_certs.split(",") if s.strip()]

                jd_parts = [
                    f"# {ai_title}", "",
                    f"**Location:** {ai_location or 'Not specified'}",
                    f"**Department:** {ai_team or 'Engineering'}",
                    f"**Level:** {ai_level}",
                    f"**Industry:** {ai_industry or 'Technology'}", "",
                    f"## About the Role",
                    f"We are seeking a {ai_level} {ai_title} to join our {ai_team or 'engineering'} team. "
                    f"This role requires {ai_exp_min}{'–' + str(ai_exp_max) if ai_exp_max > ai_exp_min else '+'} years of experience.", "",
                    "## Requirements", "", "### Required Skills",
                ]
                for sk in (must or [f"Relevant skills for {ai_title} role"]):
                    jd_parts.append(f"- {sk}")
                jd_parts.extend(["", "### Preferred Skills"])
                for sk in (nice or ["Additional complementary skills"]):
                    jd_parts.append(f"- {sk}")
                jd_parts.extend(["", "### Experience", f"- Minimum {ai_exp_min} years of relevant experience"])
                if ai_exp_max > ai_exp_min:
                    jd_parts.append(f"- Ideally {ai_exp_min}–{ai_exp_max} years")
                jd_parts.extend(["", "### Education", f"- {ai_education} degree or equivalent"])
                if certs:
                    jd_parts.extend(["", "### Certifications (Preferred)"])
                    for c in certs:
                        jd_parts.append(f"- {c}")
                jd_parts.extend(["", "### Responsibilities",
                    f"- Design, implement, and maintain solutions aligned with the role",
                    f"- Collaborate with cross-functional teams",
                    f"- Mentor junior team members",
                    f"- Participate in planning and continuous improvement",
                ])
                if ai_extra.strip():
                    jd_parts.extend(["", "### Additional Requirements", ai_extra.strip()])

                generated_jd = "\n".join(jd_parts)
                st.text_area("Review and edit:", value=generated_jd, height=350, key="ai_generated_jd")

                ai_jd_name = st.text_input("Save as:", value=f"{ai_title} - {ai_level}", key="ai_save_name")
                if st.button("💾 Save Generated JD"):
                    tags = [ai_level.lower()]
                    if ai_industry:
                        tags.append(ai_industry.lower())
                    try:
                        cfg = load_config()
                        jd_criteria = analyze_jd(generated_jd, cfg)
                        from history import _safe_asdict
                        jd_data = _safe_asdict(jd_criteria)
                    except Exception:
                        jd_data = {}
                    save_jd(ai_jd_name.strip(), generated_jd.strip(), jd_data, tags)
                    st.success(f"✅ Saved '{ai_jd_name}'!")


# =====================================================================
# PAGE: SCREENING
# =====================================================================
elif selected_page == "🔍 Screening":
    _hero("🔍 Candidate Screening",
          "Select a JD · Upload Resumes · Run the full screening pipeline",
          "STEP-BY-STEP")

    # Step indicators
    st.markdown("""
    <div class="step-row">
        <div class="step-item active"><span class="step-num">1</span> Select JD</div>
        <div class="step-connector"></div>
        <div class="step-item"><span class="step-num">2</span> Upload Resumes</div>
        <div class="step-connector"></div>
        <div class="step-item"><span class="step-num">3</span> Configure</div>
        <div class="step-connector"></div>
        <div class="step-item"><span class="step-num">4</span> Screen</div>
    </div>
    """, unsafe_allow_html=True)

    # Step 1: Select JD
    st.markdown('<div class="sec-header">📄 Step 1 — Select Job Description</div>', unsafe_allow_html=True)
    jd_source_method = st.radio("JD Source:", ["Select Saved JD", "Upload New JD", "Paste JD Text"], horizontal=True)

    jd_source = None
    jd_text_for_screen = ""

    if jd_source_method == "Select Saved JD":
        try:
            saved_jds = get_all_jds()
        except Exception:
            saved_jds = []

        if not saved_jds:
            st.info("No saved JDs. Go to **JD Management** to create one, or use Upload/Paste.")
        else:
            default_idx = 0
            if st.session_state.selected_jd_id:
                for i, j in enumerate(saved_jds):
                    if j["id"] == st.session_state.selected_jd_id:
                        default_idx = i
                        break

            selected = st.selectbox(
                "Choose JD:",
                options=saved_jds,
                index=default_idx,
                format_func=lambda x: f"📄 {x['name']} (used {x.get('use_count', 0)}x)",
                key="screen_jd_select",
            )
            if selected:
                jd_text_for_screen = selected["jd_text"]
                st.session_state.selected_jd_id = selected["id"]
                with st.expander("Preview JD text"):
                    st.text(jd_text_for_screen[:1000] + ("…" if len(jd_text_for_screen) > 1000 else ""))

    elif jd_source_method == "Upload New JD":
        jd_file = st.file_uploader("Upload JD (PDF/DOCX/TXT)", type=["pdf", "docx", "doc", "txt"],
                                    key="screen_jd_upload")
        if jd_file:
            jd_source = str(_save_upload(jd_file))

    else:
        jd_text_for_screen = st.text_area("Paste JD text:", height=200, key="screen_jd_paste")

    # Step 2: Upload Resumes
    st.markdown('<div class="sec-header green">📤 Step 2 — Upload Resumes</div>', unsafe_allow_html=True)
    resume_files = st.file_uploader("Upload candidate resumes (multiple)", type=["pdf", "docx", "doc", "txt"],
                                     accept_multiple_files=True, key="screen_resume_upload")

    # Cache uploaded files to session_state for persistence across page navigation
    if resume_files:
        _cache_resume_uploads(resume_files)
        st.caption(f"📎 {len(resume_files)} file(s) selected")
    elif st.session_state.uploaded_resume_data:
        # Show previously cached uploads
        cached_names = list(st.session_state.uploaded_resume_data.keys())
        st.info(f"📎 **{len(cached_names)} resume(s) cached from previous upload:** {', '.join(cached_names)}")
        st.caption("Upload new files above to replace, or proceed with cached files.")

    # Step 3: Options
    st.markdown('<div class="sec-header purple">⚙️ Step 3 — Configure Options</div>', unsafe_allow_html=True)
    opt_c1, opt_c2, opt_c3 = st.columns(3)
    with opt_c1:
        st.markdown("**Pipeline Options**")
        run_verify = st.checkbox("🔍 Background Verification", value=True)
        run_agents = st.checkbox("🤖 Agent Panel Evaluation", value=True)
    with opt_c2:
        st.markdown("**Scoring Weights** _(sum → 100)_")
        w_req = st.slider("Required Skills", 0, 50, 35, key="w_req")
        w_pref = st.slider("Preferred Skills", 0, 30, 15, key="w_pref")
        w_exp = st.slider("Experience", 0, 40, 25, key="w_exp")
    with opt_c3:
        st.markdown("&nbsp;")
        w_edu = st.slider("Education", 0, 20, 10, key="w_edu")
        w_cert = st.slider("Certifications", 0, 20, 10, key="w_cert")
        w_sem = st.slider("Semantic Match", 0, 20, 5, key="w_sem")

    # Agent selection
    selected_agent_names = None
    if run_agents:
        st.markdown('<div class="sec-header cyan">🤖 Step 3b — Select Agents</div>', unsafe_allow_html=True)
        _all_agent_names = [a["name"] for a in AGENT_CATALOGUE]

        agent_preset = st.radio(
            "Agent preset:",
            ["All 11 Agents", "Technical Only", "Cloud & AWS Only", "People Only", "Custom"],
            horizontal=True, key="agent_preset",
        )

        if agent_preset == "All 11 Agents":
            selected_agent_names = None  # None = all
        elif agent_preset == "Technical Only":
            selected_agent_names = [a["name"] for a in AGENT_CATALOGUE if a["group"] == "Software & Architecture"]
        elif agent_preset == "Cloud & AWS Only":
            selected_agent_names = [a["name"] for a in AGENT_CATALOGUE if a["group"] == "Cloud & AWS"]
        elif agent_preset == "People Only":
            selected_agent_names = [a["name"] for a in AGENT_CATALOGUE if a["group"] == "People & Hiring"]
        else:
            selected_agent_names = st.multiselect(
                "Select agents:",
                options=_all_agent_names,
                default=_all_agent_names,
                key="custom_agents",
            )
            if not selected_agent_names:
                st.warning("⚠️ Select at least one agent.")

        # Show selected agents summary
        if selected_agent_names:
            _sel_catalogue = [a for a in AGENT_CATALOGUE if a["name"] in selected_agent_names]
            _total_w = sum(a["weight"] for a in _sel_catalogue)
            st.caption(f"✅ {len(selected_agent_names)} agent(s) selected · raw weight sum: {_total_w:.0%} (will be renormalised to 100%)")

    # Step 4: Run
    st.markdown('<div class="sec-header yellow">🚀 Step 4 — Run Screening</div>', unsafe_allow_html=True)
    run_btn = st.button("🚀 Screen Candidates", type="primary", use_container_width=True)

    if run_btn:
        cfg = load_config()
        cfg.weights.required_skills = w_req
        cfg.weights.preferred_skills = w_pref
        cfg.weights.experience = w_exp
        cfg.weights.education = w_edu
        cfg.weights.certifications = w_cert
        cfg.weights.semantic = w_sem

        if jd_source:
            pass
        elif jd_text_for_screen.strip():
            jd_source = jd_text_for_screen.strip()
        else:
            st.error("❌ Please select, upload, or paste a JD.")
            st.stop()

        # Use fresh uploads OR cached resume data
        has_fresh_uploads = bool(resume_files)
        has_cached_uploads = bool(st.session_state.uploaded_resume_data)

        if not has_fresh_uploads and not has_cached_uploads:
            st.error("❌ Please upload at least one resume.")
            st.stop()

        # Cache JD source text for persistence
        st.session_state.uploaded_jd_source_text = jd_source if isinstance(jd_source, str) else ""

        if st.session_state.selected_jd_id and jd_source_method == "Select Saved JD":
            try:
                increment_jd_use_count(st.session_state.selected_jd_id)
            except Exception:
                pass

        pipeline_status = st.empty()

        # Stage 1: JD Analysis
        with st.spinner(""):
            pipeline_status.markdown("🔄 **Stage 1/5** — Analyzing Job Description…")
            jd = analyze_jd(jd_source, cfg)
            st.session_state.jd_criteria = jd
            st.session_state.jd_text = jd.raw_text[:500]

        # Stage 2: Parse Resumes — from fresh uploads or cached bytes
        if has_fresh_uploads:
            file_count = len(resume_files)
            pipeline_status.markdown(f"🔄 **Stage 2/5** — Parsing {file_count} resume(s)…")
        else:
            file_count = len(st.session_state.uploaded_resume_data)
            pipeline_status.markdown(f"🔄 **Stage 2/5** — Parsing {file_count} cached resume(s)…")

        candidates = []
        progress = st.progress(0, text="Parsing resumes…")

        if has_fresh_uploads:
            for i, rf in enumerate(resume_files):
                try:
                    p = _save_upload(rf)
                    candidates.append(parse_resume(str(p), cfg))
                    progress.progress((i + 1) / file_count, text=f"✅ Parsed {rf.name}")
                except Exception as e:
                    st.warning(f"⚠️ Failed to parse {rf.name}: {e}")
                    progress.progress((i + 1) / file_count)
        else:
            for i, (fname, fbytes) in enumerate(st.session_state.uploaded_resume_data.items()):
                try:
                    p = _save_upload_from_bytes(fname, fbytes)
                    candidates.append(parse_resume(str(p), cfg))
                    progress.progress((i + 1) / file_count, text=f"✅ Parsed {fname}")
                except Exception as e:
                    st.warning(f"⚠️ Failed to parse {fname}: {e}")
                    progress.progress((i + 1) / file_count)
        progress.empty()

        if not candidates:
            st.error("No resumes parsed successfully.")
            st.stop()

        # Stage 3: Verification
        verifications = {}
        if run_verify:
            pipeline_status.markdown(f"🔄 **Stage 3/5** — Verifying {len(candidates)} candidate(s)…")
            progress = st.progress(0, text="Verifying…")
            for i, cand in enumerate(candidates):
                try:
                    verifications[cand.name] = run_verification(cand, cfg)
                except Exception:
                    pass
                progress.progress((i + 1) / len(candidates), text=f"✅ Verified {cand.name}")
            progress.empty()

        # Stage 4: Scoring
        pipeline_status.markdown("🔄 **Stage 4/5** — Scoring & ranking…")
        scores_list = []
        for cand in candidates:
            ver = verifications.get(cand.name)
            scores_list.append(score_candidate(cand, jd, ver, cfg))
        ranked = rank_candidates(scores_list)
        st.session_state.scores = ranked

        # Stage 5: Agent evaluation
        agent_results = {}
        if run_agents:
            pipeline_status.markdown(f"🔄 **Stage 5/5** — Running 11-agent evaluation…")
            progress = st.progress(0, text="Agent evaluation…")
            for i, s in enumerate(ranked):
                try:
                    agent_results[s.candidate.name] = evaluate_candidate(
                        s.candidate, jd, s, s.verification,
                        selected_agents=selected_agent_names)
                except Exception as e:
                    st.warning(f"⚠️ Agent eval failed for {s.candidate.name}: {e}")
                progress.progress((i + 1) / len(ranked), text=f"✅ {s.candidate.name}")
            progress.empty()
        st.session_state.agent_results = agent_results

        # Generate questionnaires
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

        # Persist state to disk (survives browser refresh / server restart)
        st.session_state.pipeline_completed = True
        st.session_state.pipeline_timestamp = datetime.now().strftime("%H:%M")
        st.session_state.pipeline_candidate_count = len(ranked)
        _save_state_to_disk()

        pipeline_status.empty()
        st.success(f"✅ **Pipeline complete!** Screened {len(ranked)} candidates · {len(agent_results)} agent evals · {len(questionnaires)} questionnaires generated")

        # Auto-navigate to Results on next rerun
        st.session_state.auto_navigate_to = "📊 Results"
        st.rerun()


# =====================================================================
# PAGE: RESULTS
# =====================================================================
elif selected_page == "📊 Results":
    _hero("📊 Screening Results",
          "Candidate rankings · Score breakdowns · Verification status")

    jd = st.session_state.jd_criteria
    scores = st.session_state.scores
    agent_results = st.session_state.agent_results

    if not scores:
        _empty_state("📊", "No Results Yet", "Go to the Screening page and run a screening session to see results here.")
    else:
        # JD summary
        if jd:
            jc1, jc2, jc3, jc4 = st.columns(4)
            with jc1:
                st.markdown(_glass_metric(len(jd.required_skills), "Required Skills", jd.title[:30]), unsafe_allow_html=True)
            with jc2:
                st.markdown(_glass_metric(f"{jd.min_experience_years:.0f}+", "Min Experience", "years"), unsafe_allow_html=True)
            with jc3:
                st.markdown(_glass_metric(jd.role_level, "Role Level", jd.industry), unsafe_allow_html=True)
            with jc4:
                st.markdown(_glass_metric(jd.education_level, "Education", "requirement"), unsafe_allow_html=True)

        st.markdown("")

        # Overview metrics
        st.markdown('<div class="sec-header">📊 Screening Overview</div>', unsafe_allow_html=True)
        top = scores[0]
        ov1, ov2, ov3, ov4, ov5 = st.columns(5)
        with ov1: st.metric("Total", len(scores))
        with ov2: st.metric("Avg Score", f"{sum(s.overall_score for s in scores)/len(scores):.1f}")
        with ov3: st.metric("A/A+ Grades", sum(1 for s in scores if s.grade.startswith("A")))
        with ov4: st.metric("🏆 Top", top.candidate.name[:20])
        with ov5: st.metric("Top Score", f"{top.overall_score:.1f}")

        # Rankings table
        st.markdown('<div class="sec-header green">🏆 Candidate Rankings</div>', unsafe_allow_html=True)
        w_req = st.session_state.get("w_req", 35)
        w_pref = st.session_state.get("w_pref", 15)
        w_exp = st.session_state.get("w_exp", 25)
        w_edu = st.session_state.get("w_edu", 10)
        w_cert = st.session_state.get("w_cert", 10)
        w_sem = st.session_state.get("w_sem", 5)

        rows = []
        for s in scores:
            req_total = len(s.matched_required_skills) + len(s.missing_required_skills)
            req_match = len(s.matched_required_skills)
            li = s.verification.linkedin
            li_status = "✅" if (li and li.url_resolves) else "⚠️" if (li and li.url) else "❌"
            consensus = agent_results.get(s.candidate.name)
            agent_rec = consensus.consensus_recommendation if consensus else "N/A"

            rows.append({
                "Rank": f"#{s.rank}", "Candidate": s.candidate.name,
                "Score": f"{s.overall_score:.1f}", "Grade": s.grade,
                "Skills": f"{req_match}/{req_total}",
                "Experience": f"{s.candidate.total_experience_years:.1f}y",
                "Trust": f"{s.verification.overall_trust_score:.0%}",
                "LinkedIn": li_status, "Agent": agent_rec,
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # Stacked bar chart
        if len(scores) > 1:
            st.markdown('<div class="sec-header purple">📈 Score Comparison</div>', unsafe_allow_html=True)
            fig_bar = go.Figure()
            names = [s.candidate.name[:20] for s in scores]
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
                                   height=380, margin=dict(l=40, r=20, t=20, b=40),
                                   legend=dict(orientation="h", y=-0.2, font=dict(size=11)))
            st.plotly_chart(fig_bar, use_container_width=True)

        # Candidate detail cards
        st.markdown('<div class="sec-header">👤 Candidate Details</div>', unsafe_allow_html=True)
        for s in scores:
            medal = "🥇" if s.rank == 1 else "🥈" if s.rank == 2 else "🥉" if s.rank == 3 else f"#{s.rank}"
            with st.expander(f"{medal}  {s.candidate.name}  ·  {s.overall_score:.1f}/100  ·  {s.grade}", expanded=(s.rank == 1)):
                ic1, ic2, ic3 = st.columns(3)
                with ic1:
                    st.markdown(f"📧 {s.candidate.email or 'N/A'}")
                    st.markdown(f"📱 {s.candidate.phone or 'N/A'}")
                with ic2:
                    st.markdown(f"📍 {s.candidate.location or 'N/A'}")
                    st.markdown(f"🕐 **{s.candidate.total_experience_years:.1f} years** experience")
                with ic3:
                    li_url = s.candidate.linkedin_url or (s.verification.linkedin.url if s.verification.linkedin else "")
                    st.markdown(f"🔗 {li_url or 'N/A'}")
                    st.markdown(f"🐙 {s.candidate.github_url or 'N/A'}")

                st.markdown("---")

                # Radar + Score table
                rc1, rc2 = st.columns(2)
                with rc1:
                    b = s.breakdown
                    cats = ["Required", "Preferred", "Experience", "Education", "Certs", "Semantic"]
                    maxes = [w_req, w_pref, w_exp, w_edu, w_cert, w_sem]
                    vals = [b.required_skills, b.preferred_skills, b.experience, b.education, b.certifications, b.semantic_similarity]
                    pcts = [v / m * 100 if m > 0 else 0 for v, m in zip(vals, maxes)]
                    fig_r = go.Figure()
                    fig_r.add_trace(go.Scatterpolar(
                        r=pcts + [pcts[0]], theta=cats + [cats[0]],
                        fill="toself", fillcolor="rgba(59,130,246,0.15)",
                        line=dict(color="#3b82f6", width=2),
                    ))
                    fig_r.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100], showticklabels=False)),
                                         showlegend=False, template="plotly_dark",
                                         paper_bgcolor="rgba(0,0,0,0)", height=260,
                                         margin=dict(l=60, r=60, t=15, b=15))
                    st.plotly_chart(fig_r, use_container_width=True)
                with rc2:
                    score_df = pd.DataFrame({
                        "Category": cats, "Points": [f"{v:.1f}" for v in vals], "Max": maxes,
                        "%": [f"{p:.0f}%" for p in pcts],
                    })
                    st.dataframe(score_df, hide_index=True, use_container_width=True)
                    st.markdown(f"**Total: {s.overall_score:.1f} / 100**")

                    if jd:
                        gap = compute_skill_gap(s.candidate.skills, s.candidate.raw_text, jd)
                        sev = {"Critical": "🔴", "Moderate": "🟡", "Low": "🟢"}.get(gap["gap_severity"], "⚪")
                        st.markdown(f"**Skill Gap:** {sev} {gap['gap_severity']} ({gap['required_match_pct']}% req match)")

                # Skills matched/missing
                sk1, sk2 = st.columns(2)
                with sk1:
                    if s.matched_required_skills:
                        st.success(f"✅ **Matched:** {', '.join(s.matched_required_skills)}")
                    else:
                        st.warning("No required skills matched")
                with sk2:
                    if s.missing_required_skills:
                        st.error(f"❌ **Missing:** {', '.join(s.missing_required_skills)}")
                    else:
                        st.success("✅ All required skills matched!")

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
                        if li.url_resolves:
                            st.write(f"✅ Verified ({li.authenticity_score:.0%})")
                        elif li.url:
                            st.write(f"⚠️ Found: {li.url}")
                        else:
                            st.write("❌ Not found")
                    st.markdown("**🆔 Identity**")
                    ident = s.verification.identity
                    if ident:
                        st.write(f"Score: **{ident.overall_identity_score:.0%}** ({ident.method})")
                with vc3:
                    st.markdown("**📧 Email**")
                    if ident and ident.email:
                        em = ident.email
                        st.write(f"{'✅' if em.format_valid else '❌'} Format · {'✅' if em.mx_record_exists else '❌'} MX · {em.domain_type}")
                    st.markdown("**📅 Timeline**")
                    if ident and ident.timeline:
                        tl = ident.timeline
                        st.write(f"{'✅' if tl.timeline_plausible else '⚠️'} {tl.calculated_years:.1f}y calculated")
                        for gap in tl.gap_details:
                            st.warning(gap)

        # Export
        st.markdown("---")
        if st.button("📥 Download JSON Report", use_container_width=True):
            from report_generator import _score_to_dict
            data = {
                "generated_at": datetime.now().isoformat(),
                "job_title": jd.title if jd else "",
                "candidates": [_score_to_dict(s) for s in scores],
            }
            st.download_button("📥 Download", json.dumps(data, indent=2, default=str),
                                file_name="screening_report.json", mime="application/json")


# =====================================================================
# PAGE: AGENT PANEL
# =====================================================================
elif selected_page == "🤖 Agent Panel":
    _hero("🤖 Multi-Agent Evaluation Panel",
          "11 specialist agents evaluate each candidate · Consensus-driven assessment",
          "COLLABORATIVE AI")

    agent_results = st.session_state.agent_results

    if not agent_results:
        _empty_state("🤖", "No Agent Evaluations", "Run screening with 'Agent Panel Evaluation' enabled to see results here.")
    else:
        selected_candidate = st.selectbox(
            "Select Candidate",
            options=list(agent_results.keys()),
            key="agent_candidate_select",
        )

        if selected_candidate and selected_candidate in agent_results:
            consensus: ConsensusResult = agent_results[selected_candidate]

            # Consensus cards
            cc1, cc2, cc3, cc4 = st.columns(4)
            with cc1:
                st.markdown(_glass_metric(f"{consensus.consensus_score:.0f}", "Consensus Score"), unsafe_allow_html=True)
            with cc2:
                st.markdown(f'<div class="glass-card"><div class="value" style="color:{_grade_color(consensus.consensus_grade)}">{consensus.consensus_grade}</div><div class="label">Grade</div></div>', unsafe_allow_html=True)
            with cc3:
                st.markdown(f'<div class="glass-card"><div class="value" style="font-size:1.3rem;color:{_rec_color(consensus.consensus_recommendation)}">{consensus.consensus_recommendation}</div><div class="label">Recommendation</div></div>', unsafe_allow_html=True)
            with cc4:
                st.markdown(_glass_metric(f"{consensus.confidence:.0%}", "Confidence"), unsafe_allow_html=True)

            st.markdown("")
            st.markdown(consensus.summary)

            if consensus.risk_flags:
                for flag in consensus.risk_flags:
                    st.warning(f"🚩 {flag}")

            # Agent evaluations as card grid
            st.markdown('<div class="sec-header">👥 Agent Evaluations</div>', unsafe_allow_html=True)

            for row_start in range(0, len(consensus.evaluations), 2):
                row_evs = consensus.evaluations[row_start:row_start + 2]
                cols = st.columns(len(row_evs))
                for col, ev in zip(cols, row_evs):
                    with col:
                        icon = _agent_icon(ev.agent_name)
                        color = _AGENT_COLORS.get(ev.agent_name, "blue")
                        with st.expander(f"{icon} {ev.agent_name} — {ev.score}/100 · {ev.recommendation}", expanded=False):
                            em1, em2 = st.columns(2)
                            with em1:
                                st.markdown("**Strengths**")
                                for s_item in ev.strengths[:5]:
                                    st.markdown(f"✅ {s_item}")
                            with em2:
                                st.markdown("**Concerns**")
                                for c_item in ev.concerns[:5]:
                                    st.markdown(f"⚠️ {c_item}")
                            if ev.skill_gaps:
                                st.caption(f"**Skill Gaps:** {', '.join(ev.skill_gaps[:5])}")
                            if ev.key_questions:
                                st.caption(f"**Top Question:** {ev.key_questions[0]}")

            # Radar chart
            st.markdown('<div class="sec-header purple">📊 Agent Score Radar</div>', unsafe_allow_html=True)
            agent_names = [ev.agent_name[:15] for ev in consensus.evaluations]
            agent_scores = [ev.score for ev in consensus.evaluations]

            fig_agent = go.Figure()
            fig_agent.add_trace(go.Scatterpolar(
                r=agent_scores + [agent_scores[0]],
                theta=agent_names + [agent_names[0]],
                fill="toself", fillcolor="rgba(56,189,248,0.15)",
                line=dict(color="#38bdf8", width=2),
                name=selected_candidate,
            ))
            fig_agent.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=9))),
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                height=420, margin=dict(l=90, r=90, t=30, b=30),
            )
            st.plotly_chart(fig_agent, use_container_width=True)

            # Discussion log
            if consensus.discussion:
                st.markdown('<div class="sec-header">💬 Agent Discussion Log</div>', unsafe_allow_html=True)
                for msg in consensus.discussion:
                    st.markdown(
                        f'<div class="disc-bubble">'
                        f'<span class="agent">{_agent_icon(msg.agent_name)} {msg.agent_name}</span> '
                        f'<span class="round">Round {msg.round_number}</span><br/>'
                        f'{msg.message}</div>',
                        unsafe_allow_html=True,
                    )

            # Interview focus areas
            if consensus.interview_focus_areas:
                st.markdown('<div class="sec-header green">🎯 Interview Focus Areas</div>', unsafe_allow_html=True)
                for i, q in enumerate(consensus.interview_focus_areas, 1):
                    st.write(f"**{i}.** {q}")


# =====================================================================
# PAGE: HISTORY
# =====================================================================
elif selected_page == "📅 History":
    _hero("📅 Screening History",
          "All past screening sessions · Searchable by date, month, year")

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
        search_name = st.text_input("🔍 Search candidate:", key="hist_search")

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
        st.markdown(f"**{len(sessions)} session(s) found**")

        sess_rows = []
        for sess in sessions:
            sess_rows.append({
                "ID": sess["id"],
                "Date": sess["created_at"][:16],
                "JD Title": sess["jd_title"],
                "Role": sess["jd_role"],
                "Candidates": sess["total_candidates"],
                "Avg Score": f"{sess['avg_score']:.1f}",
                "Top": sess["top_candidate"],
                "Top Score": f"{sess['top_score']:.1f}",
            })
        st.dataframe(pd.DataFrame(sess_rows), use_container_width=True, hide_index=True)

        selected_session = st.selectbox(
            "View session details:",
            options=[s["id"] for s in sessions],
            format_func=lambda x: f"Session {x} — {next((s['jd_title'] for s in sessions if s['id']==x), '')}",
            key="hist_session_select",
        )

        if selected_session:
            hbtn_col1, hbtn_col2 = st.columns([3, 1])
            with hbtn_col2:
                if st.session_state.scores and st.session_state.get("last_session_id") == selected_session:
                    if st.button("📊 View in Results", use_container_width=True):
                        st.session_state.auto_navigate_to = "📊 Results"
                        st.rerun()

            try:
                cands = get_candidates_for_session(selected_session)
            except Exception:
                cands = []

            if cands:
                st.markdown(f"### 📋 Session {selected_session} — {len(cands)} candidates")
                for cand in cands:
                    with st.expander(f"#{cand['rank']} · {cand['name']} · {cand['overall_score']}/100 · {cand['grade']}"):
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

                        if isinstance(cand['matched_required'], list) and cand['matched_required']:
                            st.success(f"✅ Matched: {', '.join(cand['matched_required'])}")
                        if isinstance(cand['missing_required'], list) and cand['missing_required']:
                            st.error(f"❌ Missing: {', '.join(cand['missing_required'])}")

                        if isinstance(cand['agent_consensus'], dict) and cand['agent_consensus']:
                            ac = cand['agent_consensus']
                            if 'consensus_score' in ac:
                                st.info(f"🤖 **Agent Consensus:** {ac.get('consensus_score', 'N/A')}/100 — "
                                       f"{ac.get('consensus_recommendation', 'N/A')} "
                                       f"(Confidence: {ac.get('confidence', 'N/A')})")
    else:
        _empty_state("📅", "No Screening History", "Run a screening session to start tracking results over time.")

    if search_name:
        st.markdown("---")
        st.markdown(f'<div class="sec-header">🔍 Results for "{search_name}"</div>', unsafe_allow_html=True)
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
# PAGE: ANALYTICS
# =====================================================================
elif selected_page == "📈 Analytics":
    _hero("📈 Screening Analytics",
          "Aggregate statistics · Trends · Grade distributions · Skills heatmap")

    try:
        stats = get_stats_summary()
    except Exception:
        stats = {"total_sessions": 0, "total_candidates": 0, "unique_candidates": 0,
                 "avg_score": 0, "top_candidate": None, "grade_distribution": {},
                 "monthly_trend": [], "pass_rate": 0, "top_demanded_skills": [],
                 "top_missing_skills": [], "top_matched_skills": []}

    # Row 1: Key metrics (6 cols now)
    ac1, ac2, ac3, ac4, ac5, ac6 = st.columns(6)
    with ac1:
        st.markdown(_glass_metric(stats["total_sessions"], "Sessions", "screening runs"), unsafe_allow_html=True)
    with ac2:
        st.markdown(_glass_metric(stats["total_candidates"], "Candidates", "total scans"), unsafe_allow_html=True)
    with ac3:
        st.markdown(_glass_metric(stats.get("unique_candidates", "—"), "Unique", "distinct names"), unsafe_allow_html=True)
    with ac4:
        st.markdown(_glass_metric(f'{stats["avg_score"]:.1f}' if stats["avg_score"] else "0", "Avg Score", "out of 100"), unsafe_allow_html=True)
    with ac5:
        st.markdown(_glass_metric(f'{stats.get("pass_rate", 0)}%', "Pass Rate", "score ≥ 70"), unsafe_allow_html=True)
    with ac6:
        top_c = stats.get("top_candidate")
        top_name = "N/A"
        if isinstance(top_c, dict):
            top_name = top_c.get("name", "N/A")
        elif top_c is not None:
            try:
                top_name = dict(top_c).get("name", "N/A")
            except Exception:
                pass
        st.markdown(_glass_metric(top_name[:16], "All-Time Top"), unsafe_allow_html=True)

    st.markdown("")

    # Row 2: Charts — Grade distribution + Monthly trend
    ch1, ch2 = st.columns(2)

    grade_dist = stats.get("grade_distribution", {})
    with ch1:
        st.markdown('<div class="sec-header">📊 Grade Distribution</div>', unsafe_allow_html=True)
        if grade_dist:
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
                                     margin=dict(l=30, r=20, t=20, b=30))
            st.plotly_chart(fig_grade, use_container_width=True)
        else:
            st.info("No grade data yet.")

    monthly = stats.get("monthly_trend", [])
    with ch2:
        st.markdown('<div class="sec-header purple">📈 Monthly Trend</div>', unsafe_allow_html=True)
        if monthly:
            months = [m["month"] for m in monthly]
            counts = [m["candidates"] for m in monthly]
            avgs = [round(m["avg_score"], 1) for m in monthly]

            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(x=months, y=counts, name="Candidates", marker_color="#3b82f6", opacity=0.7))
            fig_trend.add_trace(go.Scatter(x=months, y=avgs, name="Avg Score",
                                            mode="lines+markers", yaxis="y2",
                                            line=dict(color="#f59e0b", width=2.5),
                                            marker=dict(size=7)))
            fig_trend.update_layout(
                template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=300, margin=dict(l=30, r=40, t=20, b=30),
                yaxis=dict(title="Candidates"), yaxis2=dict(title="Avg Score", overlaying="y", side="right"),
                legend=dict(orientation="h", y=-0.2, font=dict(size=10)),
            )
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No trend data yet.")

    st.markdown("")

    # Row 3: Skills Heatmap — Demanded vs Matched vs Missing
    st.markdown('<div class="sec-header cyan">🔥 Skills Heatmap</div>', unsafe_allow_html=True)
    top_demanded = stats.get("top_demanded_skills", [])
    top_matched = stats.get("top_matched_skills", [])
    top_missing = stats.get("top_missing_skills", [])

    if top_demanded or top_matched or top_missing:
        sk1, sk2, sk3 = st.columns(3)
        with sk1:
            st.markdown("**📋 Most Demanded**")
            if top_demanded:
                _sk_names = [s[0].title() for s in top_demanded[:10]]
                _sk_counts = [s[1] for s in top_demanded[:10]]
                fig_dem = go.Figure(go.Bar(x=_sk_counts, y=_sk_names, orientation="h",
                                            marker_color="#3b82f6", text=_sk_counts, textposition="auto"))
                fig_dem.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                       plot_bgcolor="rgba(0,0,0,0)", height=300,
                                       margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_dem, use_container_width=True)
            else:
                st.caption("No JD data yet.")
        with sk2:
            st.markdown("**✅ Most Matched**")
            if top_matched:
                _sk_names = [s[0].title() for s in top_matched[:10]]
                _sk_counts = [s[1] for s in top_matched[:10]]
                fig_mat = go.Figure(go.Bar(x=_sk_counts, y=_sk_names, orientation="h",
                                            marker_color="#10b981", text=_sk_counts, textposition="auto"))
                fig_mat.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                       plot_bgcolor="rgba(0,0,0,0)", height=300,
                                       margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_mat, use_container_width=True)
            else:
                st.caption("No match data yet.")
        with sk3:
            st.markdown("**❌ Most Missing**")
            if top_missing:
                _sk_names = [s[0].title() for s in top_missing[:10]]
                _sk_counts = [s[1] for s in top_missing[:10]]
                fig_mis = go.Figure(go.Bar(x=_sk_counts, y=_sk_names, orientation="h",
                                            marker_color="#ef4444", text=_sk_counts, textposition="auto"))
                fig_mis.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                       plot_bgcolor="rgba(0,0,0,0)", height=300,
                                       margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_mis, use_container_width=True)
            else:
                st.caption("No gap data yet.")
    else:
        st.info("Run screenings to generate skills heatmap data.")

    st.markdown("")

    # Row 4: Agent Analytics (from current session)
    st.markdown('<div class="sec-header green">🤖 Agent Analytics</div>', unsafe_allow_html=True)
    _current_agent_results = st.session_state.agent_results
    if _current_agent_results:
        # Build per-agent score table across all candidates in current session
        _agent_score_map = {}  # {agent_name: [scores]}
        _agent_rec_map = {}    # {agent_name: {rec: count}}
        for cand_name, consensus in _current_agent_results.items():
            if hasattr(consensus, "evaluations"):
                for ev in consensus.evaluations:
                    _agent_score_map.setdefault(ev.agent_name, []).append(ev.score)
                    _agent_rec_map.setdefault(ev.agent_name, {})
                    _agent_rec_map[ev.agent_name][ev.recommendation] = _agent_rec_map[ev.agent_name].get(ev.recommendation, 0) + 1

        if _agent_score_map:
            ag1, ag2 = st.columns(2)
            with ag1:
                st.markdown("**Agent Avg Scores (Current Session)**")
                _agent_names = list(_agent_score_map.keys())
                _agent_avgs = [round(sum(v)/len(v), 1) for v in _agent_score_map.values()]
                _colors = ["#ef4444" if a < 50 else "#f59e0b" if a < 70 else "#10b981" for a in _agent_avgs]
                fig_ag = go.Figure(go.Bar(
                    x=_agent_avgs, y=_agent_names, orientation="h",
                    marker_color=_colors, text=_agent_avgs, textposition="auto",
                ))
                fig_ag.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                                      plot_bgcolor="rgba(0,0,0,0)", height=350,
                                      margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig_ag, use_container_width=True)
            with ag2:
                st.markdown("**Agent Recommendation Distribution**")
                _rec_rows = []
                for aname, recs in _agent_rec_map.items():
                    for rec, cnt in recs.items():
                        _rec_rows.append({"Agent": aname, "Recommendation": rec, "Count": cnt})
                if _rec_rows:
                    _rec_df = pd.DataFrame(_rec_rows)
                    _pivot = _rec_df.pivot_table(index="Agent", columns="Recommendation",
                                                  values="Count", fill_value=0, aggfunc="sum")
                    _rec_order = ["Strong Hire", "Hire", "Lean Hire", "No Hire"]
                    _rec_colors = {"Strong Hire": "#10b981", "Hire": "#3b82f6", "Lean Hire": "#f59e0b", "No Hire": "#ef4444"}
                    fig_rec = go.Figure()
                    for rec in _rec_order:
                        if rec in _pivot.columns:
                            fig_rec.add_trace(go.Bar(
                                y=_pivot.index, x=_pivot[rec], name=rec,
                                orientation="h", marker_color=_rec_colors.get(rec, "#94a3b8"),
                            ))
                    fig_rec.update_layout(
                        barmode="stack", template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        height=350, margin=dict(l=10, r=10, t=10, b=10),
                        yaxis=dict(autorange="reversed"),
                        legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
                    )
                    st.plotly_chart(fig_rec, use_container_width=True)
    else:
        st.info("Run a screening session to see per-agent analytics here.")

    st.markdown("")

    # Row 5: All candidates table
    st.markdown('<div class="sec-header yellow">📋 All Scanned Candidates</div>', unsafe_allow_html=True)
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
                "Date": (c.get("session_date") or c.get("scanned_at", ""))[:16],
            })
        st.dataframe(pd.DataFrame(cand_rows), use_container_width=True, hide_index=True)
    else:
        _empty_state("📋", "No Candidate Data", "Run screenings to populate analytics.")


# =====================================================================
# PAGE: INTERVIEW PREP
# =====================================================================
elif selected_page == "❓ Interview Prep":
    _hero("❓ Interview Questionnaire",
          "Auto-generated questions based on skill gaps, agent evaluations & role requirements",
          "DOCX + JSON EXPORT")

    questionnaires = st.session_state.questionnaires

    if not questionnaires:
        _empty_state("❓", "No Questionnaires", "Run a screening session to auto-generate interview questionnaires.")
    else:
        sel_cand = st.selectbox("Select Candidate:", options=list(questionnaires.keys()),
                                 key="interview_select")

        if sel_cand and sel_cand in questionnaires:
            q = questionnaires[sel_cand]

            # Summary metrics
            qm1, qm2, qm3 = st.columns(3)
            with qm1:
                st.markdown(_glass_metric(q.total_questions, "Questions", q.role_title[:25]), unsafe_allow_html=True)
            with qm2:
                st.markdown(_glass_metric(len(q.sections), "Sections"), unsafe_allow_html=True)
            with qm3:
                st.markdown(_glass_metric(len(q.skill_gaps_addressed), "Skill Gaps", "to probe"), unsafe_allow_html=True)

            st.markdown("")

            if q.skill_gaps_addressed:
                st.warning(f"🎯 **Skill gaps to probe:** {', '.join(q.skill_gaps_addressed)}")

            # Questions by section
            for section_name, questions in q.sections.items():
                st.markdown(f'<div class="sec-header">{section_name} ({len(questions)})</div>', unsafe_allow_html=True)
                for i, qq in enumerate(questions, 1):
                    diff_icon = {"Basic": "🟢", "Intermediate": "🟡", "Advanced": "🔴"}.get(qq.difficulty, "⚪")
                    with st.expander(f"{diff_icon} Q{i}. {qq.question[:90]}{'…' if len(qq.question) > 90 else ''}"):
                        st.markdown(f"**{qq.question}**")
                        st.markdown("")
                        tc1, tc2 = st.columns(2)
                        with tc1:
                            st.caption(f"🎯 **Target:** {qq.target_skill}")
                            st.caption(f"📊 **Difficulty:** {qq.difficulty}")
                        with tc2:
                            st.caption(f"💡 **Rationale:** {qq.rationale}")
                            if qq.suggested_followup:
                                st.caption(f"↩️ **Follow-up:** {qq.suggested_followup}")

            # Export
            st.markdown("---")
            st.markdown('<div class="sec-header green">📥 Export Questionnaire</div>', unsafe_allow_html=True)
            ec1, ec2 = st.columns(2)

            with ec1:
                export_data = {
                    "candidate": q.candidate_name, "role": q.role_title,
                    "generated_at": q.generated_at, "total_questions": q.total_questions,
                    "sections": {
                        sec: [{"question": qq.question, "rationale": qq.rationale,
                               "difficulty": qq.difficulty, "target_skill": qq.target_skill,
                               "followup": qq.suggested_followup} for qq in qs]
                        for sec, qs in q.sections.items()
                    },
                }
                st.download_button(
                    "📥 Download JSON",
                    json.dumps(export_data, indent=2),
                    file_name=f"interview_{sel_cand.replace(' ', '_')}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            with ec2:
                try:
                    docx_bytes = export_questionnaire_docx(q)
                    st.download_button(
                        "📄 Download DOCX",
                        docx_bytes,
                        file_name=f"Interview_Questionnaire_{sel_cand.replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True,
                        type="primary",
                    )
                except Exception as e:
                    st.error(f"DOCX generation failed: {e}")
