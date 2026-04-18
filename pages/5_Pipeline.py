"""
Page 5: Candidate Pipeline — Visual pipeline management with stage transitions.
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import (
    Stage,
    list_candidates,
    transition,
    get_pipeline_stats,
    get_stage_distribution,
)

st.header("📊 Candidate Pipeline")

# ---------------------------------------------------------------------------
# Pipeline metrics
# ---------------------------------------------------------------------------

try:
    stats = get_pipeline_stats()
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total", stats.total)
    with col2:
        st.metric("Active", stats.active)
    with col3:
        st.metric("Hired", stats.hired)
    with col4:
        st.metric("Rejected", stats.rejected)
    with col5:
        if stats.avg_time_to_hire_days:
            st.metric("Avg Time-to-Hire", f"{stats.avg_time_to_hire_days:.0f}d")
        else:
            st.metric("Avg Time-to-Hire", "—")
except Exception:
    pass

st.divider()

# ---------------------------------------------------------------------------
# Funnel visualization (using stage distribution)
# ---------------------------------------------------------------------------

try:
    stage_dist = get_stage_distribution()
    if stage_dist and any(stage_dist.values()):
        st.subheader("Recruitment Funnel")

        max_count = max(stage_dist.values()) if stage_dist else 1
        stage_colors = {
            "UPLOADED": "#94a3b8", "PARSED": "#64748b", "SCORED": "#38bdf8",
            "SHORTLISTED": "#a78bfa", "INTERVIEW": "#f59e0b", "INTERVIEWED": "#fb923c",
            "OFFER": "#22c55e", "HIRED": "#10b981", "REJECTED": "#ef4444", "WITHDRAWN": "#6b7280",
        }

        for stage_name, count in stage_dist.items():
            if count == 0:
                continue
            pct = (count / max_count * 100) if max_count > 0 else 0
            color = stage_colors.get(stage_name, "#64748b")

            st.markdown(
                f'<div style="margin-bottom:4px">'
                f'<span style="color:{color};font-weight:600;width:120px;display:inline-block">{stage_name}</span>'
                f'<span style="color:#94a3b8">{count}</span></div>'
                f'<div style="background:#1e293b;border-radius:6px;height:20px;overflow:hidden;margin-bottom:8px">'
                f'<div style="background:{color};height:100%;width:{pct:.0f}%;border-radius:6px;'
                f'transition:width 0.5s ease"></div></div>',
                unsafe_allow_html=True,
            )

        st.divider()
except Exception:
    pass

# ---------------------------------------------------------------------------
# Kanban-style board
# ---------------------------------------------------------------------------

st.subheader("Pipeline Board")

candidates = list_candidates()

if not candidates:
    st.info("No candidates in the pipeline yet. Go to **Screening** to process resumes.")
    st.stop()

# Group by stage
by_stage: dict[str, list] = defaultdict(list)
for c in candidates:
    by_stage[c.current_stage.value].append(c)

# Display as columns for active stages
active_stages = ["SCORED", "SHORTLISTED", "INTERVIEW", "INTERVIEWED", "OFFER"]
stage_cols = st.columns(len(active_stages))

for col, stage_name in zip(stage_cols, active_stages):
    with col:
        stage_color = {
            "SCORED": "#38bdf8", "SHORTLISTED": "#a78bfa",
            "INTERVIEW": "#f59e0b", "INTERVIEWED": "#fb923c", "OFFER": "#22c55e",
        }.get(stage_name, "#64748b")

        items = by_stage.get(stage_name, [])
        st.markdown(
            f'<div style="text-align:center;color:{stage_color};font-weight:700;'
            f'border-bottom:2px solid {stage_color};padding-bottom:4px;margin-bottom:8px">'
            f'{stage_name} ({len(items)})</div>',
            unsafe_allow_html=True,
        )

        for item in items:
            score_str = f"{item.score:.0f}" if item.score else "—"
            st.markdown(
                f'<div style="background:rgba(30,41,59,0.7);border:1px solid #334155;'
                f'border-radius:8px;padding:0.5rem;margin-bottom:6px">'
                f'<div style="font-weight:600;font-size:0.85rem">{item.name}</div>'
                f'<div style="font-size:0.75rem;color:#94a3b8">Score: {score_str}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

# Terminal stages
terminal = ["HIRED", "REJECTED", "WITHDRAWN"]
has_terminal = any(by_stage.get(s) for s in terminal)
if has_terminal:
    st.divider()
    st.markdown("**Completed**")
    term_cols = st.columns(3)
    for col, stage_name in zip(term_cols, terminal):
        with col:
            items = by_stage.get(stage_name, [])
            st.markdown(f"**{stage_name} ({len(items)})**")
            for item in items:
                st.markdown(f"- {item.name}")

# ---------------------------------------------------------------------------
# Stage transition controls
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Move Candidate")

active_candidates = [c for c in candidates if c.current_stage.value not in ("HIRED", "REJECTED", "WITHDRAWN")]
if active_candidates:
    col1, col2, col3 = st.columns([3, 3, 2])
    with col1:
        candidate_names = [c.name for c in active_candidates]
        selected = st.selectbox("Candidate", candidate_names, key="pipe_move_name")
    with col2:
        target_stages = [s.value for s in Stage if s.value not in ("UPLOADED", "PARSED")]
        target = st.selectbox("Move to", target_stages, key="pipe_move_target")
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Move", type="primary"):
            cand_data = next(c for c in active_candidates if c.name == selected)
            try:
                transition(cand_data.id, Stage(target))
                st.success(f"Moved {selected} → {target}")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
