"""
Page 8: Analytics — Funnel visualization, score distributions, trends.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import get_stage_distribution, get_pipeline_stats
from history import get_all_sessions, get_candidates_for_session

st.header("📈 Analytics")

# ---------------------------------------------------------------------------
# Tab layout
# ---------------------------------------------------------------------------

tab_session, tab_funnel, tab_history = st.tabs(["Session Analytics", "Pipeline Funnel", "Historical Trends"])

# ---------------------------------------------------------------------------
# Session Analytics
# ---------------------------------------------------------------------------

with tab_session:
    if "scored_candidates" not in st.session_state:
        st.info("No screening data in current session. Run **Screening** first.")
    else:
        scores = st.session_state["scored_candidates"]
        red_flags = st.session_state.get("red_flag_reports", {})

        st.subheader("Score Distribution")

        # Histogram
        try:
            import plotly.express as px
            import plotly.graph_objects as go

            score_vals = [s.overall_score for s in scores]
            names = [s.candidate.name for s in scores]

            # Bar chart of scores
            fig = go.Figure(data=[
                go.Bar(
                    x=names,
                    y=score_vals,
                    marker_color=[
                        "#22c55e" if v >= 80 else "#38bdf8" if v >= 65 else "#eab308" if v >= 50 else "#ef4444"
                        for v in score_vals
                    ],
                    text=[f"{v:.0f}" for v in score_vals],
                    textposition="outside",
                )
            ])
            fig.update_layout(
                yaxis_title="Score",
                yaxis_range=[0, 105],
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8"),
                height=400,
            )
            st.plotly_chart(fig, use_container_width=True)

        except ImportError:
            for s in scores:
                pct = min(s.overall_score, 100)
                color = "#22c55e" if pct >= 80 else "#38bdf8" if pct >= 65 else "#eab308" if pct >= 50 else "#ef4444"
                st.markdown(
                    f'**{s.candidate.name}** ({s.overall_score:.1f})'
                    f'<div style="background:#1e293b;border-radius:4px;height:16px;overflow:hidden">'
                    f'<div style="background:{color};height:100%;width:{pct:.0f}%"></div></div>',
                    unsafe_allow_html=True,
                )

        # Grade distribution
        st.subheader("Grade Distribution")
        from collections import Counter
        grades = Counter(s.grade for s in scores)
        grade_order = ["A+", "A", "B+", "B", "C", "D", "F"]

        cols = st.columns(len(grade_order))
        for col, g in zip(cols, grade_order):
            count = grades.get(g, 0)
            with col:
                grade_colors = {"A+": "#22c55e", "A": "#22c55e", "B+": "#38bdf8", "B": "#38bdf8",
                                "C": "#eab308", "D": "#f97316", "F": "#ef4444"}
                color = grade_colors.get(g, "#64748b")
                st.markdown(
                    f'<div style="text-align:center;padding:0.5rem;background:rgba(30,41,59,0.5);'
                    f'border-radius:8px;border:1px solid {color}33">'
                    f'<div style="font-size:1.5rem;font-weight:800;color:{color}">{g}</div>'
                    f'<div style="font-size:1.2rem;color:#94a3b8">{count}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # Component averages
        st.subheader("Average Component Scores")

        component_avgs = {
            "Required Skills": sum(s.breakdown.required_skills for s in scores) / len(scores),
            "Preferred Skills": sum(s.breakdown.preferred_skills for s in scores) / len(scores),
            "Experience": sum(s.breakdown.experience for s in scores) / len(scores),
            "Education": sum(s.breakdown.education for s in scores) / len(scores),
            "Certifications": sum(s.breakdown.certifications for s in scores) / len(scores),
            "Semantic": sum(s.breakdown.semantic_similarity for s in scores) / len(scores),
        }

        for comp_name, avg_val in component_avgs.items():
            col1, col2, col3 = st.columns([3, 7, 1])
            with col1:
                st.markdown(f"**{comp_name}**")
            with col2:
                color = "#22c55e" if avg_val >= 70 else "#eab308" if avg_val >= 50 else "#ef4444"
                st.markdown(
                    f'<div style="background:#1e293b;border-radius:4px;height:18px;overflow:hidden">'
                    f'<div style="background:{color};height:100%;width:{min(avg_val, 100):.0f}%"></div></div>',
                    unsafe_allow_html=True,
                )
            with col3:
                st.markdown(f"{avg_val:.0f}")

        # Red flag summary
        if red_flags:
            st.subheader("Red Flag Summary")
            risk_counts = Counter()
            for rf in red_flags.values():
                if rf:
                    risk_counts[rf.risk_level] += 1

            risk_colors = {"high": "#ef4444", "medium": "#eab308", "low": "#22c55e", "clean": "#38bdf8"}
            cols = st.columns(4)
            for col, level in zip(cols, ["high", "medium", "low", "clean"]):
                with col:
                    color = risk_colors[level]
                    st.markdown(
                        f'<div style="text-align:center;padding:0.5rem;background:rgba(30,41,59,0.5);'
                        f'border-radius:8px;border:1px solid {color}33">'
                        f'<div style="font-size:0.85rem;color:{color};font-weight:700">{level.upper()}</div>'
                        f'<div style="font-size:1.5rem;font-weight:800">{risk_counts.get(level, 0)}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

# ---------------------------------------------------------------------------
# Pipeline Funnel
# ---------------------------------------------------------------------------

with tab_funnel:
    try:
        stage_dist = get_stage_distribution()
        if stage_dist and any(stage_dist.values()):
            try:
                import plotly.graph_objects as go

                stages = list(stage_dist.keys())
                counts = list(stage_dist.values())

                fig = go.Figure(go.Funnel(
                    y=stages,
                    x=counts,
                    textinfo="value+percent initial",
                    marker=dict(color=[
                        "#94a3b8", "#64748b", "#38bdf8", "#a78bfa",
                        "#f59e0b", "#fb923c", "#22c55e", "#10b981",
                        "#ef4444", "#6b7280",
                    ][:len(stages)]),
                ))

                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8"),
                    height=500,
                )

                st.plotly_chart(fig, use_container_width=True)
            except ImportError:
                for stage_name, count in stage_dist.items():
                    st.markdown(f"**{stage_name}:** {count}")
        else:
            st.info("No pipeline data available yet.")
    except Exception:
        st.info("Pipeline data not available.")

# ---------------------------------------------------------------------------
# Historical trends
# ---------------------------------------------------------------------------

with tab_history:
    try:
        sessions = get_all_sessions()

        if sessions:
            st.subheader(f"Past Sessions ({len(sessions)})")

            for session in sessions[:20]:
                session_id = session.get("id", "unknown")
                ts = session.get("created_at", "Unknown time")
                jd_title = session.get("jd_title", "Unknown JD")
                count = session.get("candidate_count", 0)

                with st.expander(
                    f"Session {session_id} — "
                    f"{ts} — "
                    f"{count} candidates"
                ):
                    st.json(session)
        else:
            st.info("No historical sessions found. Completed sessions will appear here.")
    except Exception:
        st.info("History module not available or no data yet.")
