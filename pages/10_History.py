"""
Page 10: History — Browse and reload past screening sessions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from history import get_all_sessions, get_candidates_for_session, get_all_jds

st.header("🕰️ Screening History")

# ---------------------------------------------------------------------------
# Load history
# ---------------------------------------------------------------------------

try:
    sessions = get_all_sessions()
except Exception as e:
    st.error(f"Could not load history database: {e}")
    st.stop()

if not sessions:
    st.info("No past screening sessions found. Complete a screening to create history.")
    st.stop()

# ---------------------------------------------------------------------------
# Session list
# ---------------------------------------------------------------------------

st.subheader(f"Past Sessions ({len(sessions)})")

# Search / filter
search = st.text_input("🔍 Search sessions", placeholder="Filter by JD title, candidate name...")

filtered = sessions
if search:
    search_lower = search.lower()
    filtered = [
        s for s in sessions
        if search_lower in json.dumps(s).lower()
    ]

for session in filtered[:50]:
    session_id = session.get("id", 0)
    ts = session.get("created_at", "Unknown time")
    jd_title = session.get("jd_title", "Unknown JD")
    count = session.get("candidate_count", 0)

    with st.expander(f"📋 {jd_title} — {count} candidate(s) — {ts}"):
        # Session metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"**Session ID:** {session_id}")
        with col2:
            st.markdown(f"**Date:** {ts}")
        with col3:
            st.markdown(f"**Candidates:** {count}")

        # Candidate results
        try:
            candidates = get_candidates_for_session(session_id)
            if candidates:
                st.markdown("**Results:**")
                for cand in candidates:
                    name = cand.get("name", "Unknown")
                    score = cand.get("overall_score", 0)
                    grade = cand.get("grade", "—")

                    grade_colors = {
                        "A+": "🟢", "A": "🟢", "B+": "🔵", "B": "🔵",
                        "C": "🟡", "D": "🟠", "F": "🔴",
                    }
                    icon = grade_colors.get(grade, "⚪")

                    st.markdown(f"- {icon} **{name}** — {score:.1f}/100 ({grade})")
            else:
                st.caption("No candidate data stored for this session.")
        except Exception:
            st.caption("Could not load candidate data for this session.")

# ---------------------------------------------------------------------------
# Saved JDs
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Saved Job Descriptions")

try:
    saved_jds = get_all_jds()
    if saved_jds:
        for jd_item in saved_jds:
            name = jd_item.get("name", "Unknown")
            created = jd_item.get("created_at", "Unknown")
            use_count = jd_item.get("use_count", 0)

            st.markdown(f"- **{name}** — used {use_count} time(s) — saved {created}")
    else:
        st.caption("No saved JDs yet.")
except Exception:
    st.caption("Saved JDs feature not available.")

# ---------------------------------------------------------------------------
# Database stats
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Database Stats")

try:
    total_sessions = len(sessions)
    total_candidates = sum(s.get("candidate_count", 0) for s in sessions)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Sessions", total_sessions)
    with col2:
        st.metric("Total Candidates Screened", total_candidates)
    with col3:
        db_path = Path(__file__).resolve().parent.parent / "data" / "screening_history.db"
        if db_path.exists():
            size_mb = db_path.stat().st_size / (1024 * 1024)
            st.metric("DB Size", f"{size_mb:.2f} MB")
        else:
            st.metric("DB Size", "—")
except Exception:
    pass
