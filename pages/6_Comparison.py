"""
Page 6: Comparison Matrix — Side-by-side 9-dimension radar charts and ranking.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from comparator import compare_candidates

st.header("⚖️ Comparison Matrix")

if "scored_candidates" not in st.session_state:
    st.warning("No screening results yet. Go to **Screening** first.")
    st.stop()

scores = st.session_state["scored_candidates"]
red_flags = st.session_state.get("red_flag_reports", {})
jd = st.session_state.get("jd_criteria")

if len(scores) < 2:
    st.info("Need at least 2 candidates for comparison.")
    st.stop()

# ---------------------------------------------------------------------------
# Candidate selection
# ---------------------------------------------------------------------------

names = [s.candidate.name for s in scores]
selected = st.multiselect(
    "Select candidates to compare (2–5)",
    names,
    default=names[:min(3, len(names))],
    max_selections=5,
)

if len(selected) < 2:
    st.warning("Select at least 2 candidates.")
    st.stop()

sel_scores = [s for s in scores if s.candidate.name in selected]
sel_flags = {name: red_flags.get(name) for name in selected}

# ---------------------------------------------------------------------------
# Run comparison
# ---------------------------------------------------------------------------

comparison = compare_candidates(sel_scores, jd, sel_flags)

# ---------------------------------------------------------------------------
# Radar chart (Plotly)
# ---------------------------------------------------------------------------

st.subheader("9-Dimension Radar Chart")

try:
    import plotly.graph_objects as go

    fig = go.Figure()

    colors = ["#38bdf8", "#a78bfa", "#22c55e", "#f59e0b", "#ef4444"]

    for i, entry in enumerate(comparison.candidates):
        dims = [d.name for d in entry.dimensions]
        vals = [d.raw_score for d in entry.dimensions]
        # Close the polygon
        dims_closed = dims + [dims[0]]
        vals_closed = vals + [vals[0]]

        fig.add_trace(go.Scatterpolar(
            r=vals_closed,
            theta=dims_closed,
            fill="toself",
            name=entry.name,
            line=dict(color=colors[i % len(colors)]),
            opacity=0.7,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100]),
            bgcolor="rgba(15, 23, 42, 0.5)",
        ),
        showlegend=True,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8"),
        height=500,
    )

    st.plotly_chart(fig, use_container_width=True)

except ImportError:
    st.warning("Install `plotly` for radar charts: `pip install plotly`")
    # Fallback: table
    for entry in comparison.candidates:
        st.markdown(f"**{entry.name}**")
        for d in entry.dimensions:
            st.markdown(f"- {d.name}: {d.raw_score:.0f}/100")

# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Dimension Scores")

# Build comparison matrix
dimensions = [d.name for d in comparison.candidates[0].dimensions]
table_data = {"Dimension": dimensions}
for entry in comparison.candidates:
    table_data[entry.name] = [f"{d.raw_score:.0f}" for d in entry.dimensions]

st.dataframe(table_data, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Overall comparison
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Overall Ranking")

for entry in comparison.candidates:
    col1, col2, col3 = st.columns([3, 5, 3])
    with col1:
        st.markdown(f"**{entry.name}**")
    with col2:
        pct = entry.overall_composite
        color = "#22c55e" if pct >= 70 else "#eab308" if pct >= 50 else "#ef4444"
        st.markdown(
            f'<div style="background:#1e293b;border-radius:6px;height:24px;overflow:hidden">'
            f'<div style="background:{color};height:100%;width:{pct:.0f}%;border-radius:6px"></div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(f"**{entry.overall_composite:.1f}/100**")

# ---------------------------------------------------------------------------
# Strengths / Weaknesses
# ---------------------------------------------------------------------------

st.divider()
st.subheader("Strengths & Weaknesses")

for entry in comparison.candidates:
    with st.expander(f"{entry.name} ({entry.grade})"):
        col_s, col_w = st.columns(2)
        with col_s:
            st.markdown("**💪 Strengths**")
            for s in entry.strengths:
                st.markdown(f"- ✅ {s}")
        with col_w:
            st.markdown("**⚠️ Weaknesses**")
            for w in entry.weaknesses:
                st.markdown(f"- ⚠️ {w}")

# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------

if comparison.overall_recommendation:
    st.divider()
    top = comparison.stack_rank[0] if comparison.stack_rank else "N/A"
    st.success(f"**Top Pick:** {top} — {comparison.overall_recommendation}")
