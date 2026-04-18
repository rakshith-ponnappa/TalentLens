"""
Page 7: Agent Panel — Run and display all 11 specialist agent evaluations.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agents import evaluate_candidate, AGENT_CATALOGUE

st.header("🤖 Agent Panel")

if "scored_candidates" not in st.session_state:
    st.warning("No screening results yet. Go to **Screening** first.")
    st.stop()

scores = st.session_state["scored_candidates"]
jd = st.session_state.get("jd_criteria")

# ---------------------------------------------------------------------------
# Select candidate
# ---------------------------------------------------------------------------

names = [s.candidate.name for s in scores]
selected_name = st.selectbox("Select candidate for agent evaluation", names)

if not selected_name:
    st.stop()

sc = next(s for s in scores if s.candidate.name == selected_name)
cand = sc.candidate

st.markdown(f"**Evaluating:** {cand.name} (Score: {sc.overall_score:.1f}, Grade: {sc.grade})")

# ---------------------------------------------------------------------------
# Run agents
# ---------------------------------------------------------------------------

cache_key = f"agent_consensus_{selected_name}"

if st.button("🚀 Run All Agents", type="primary") or cache_key in st.session_state:
    if cache_key not in st.session_state:
        with st.spinner("Running 11 specialist agents (3-round deliberation)..."):
            consensus = evaluate_candidate(cand, jd, sc, sc.verification)
            st.session_state[cache_key] = consensus

    consensus = st.session_state[cache_key]

    # ---------------------------------------------------------------------------
    # Consensus summary
    # ---------------------------------------------------------------------------
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        grade_class = f"grade-{consensus.consensus_grade.lower().replace('+', '-plus')}"
        st.markdown(
            f'<div style="text-align:center">'
            f'<span class="grade-badge {grade_class}" style="font-size:2rem">{consensus.consensus_grade}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.caption("Consensus Grade")
    with col2:
        st.metric("Consensus Score", f"{consensus.consensus_score:.1f}/100")
    with col3:
        st.metric("Confidence", f"{consensus.confidence:.0%}")
    with col4:
        st.metric("Recommendation", consensus.consensus_recommendation)

    # Risk flags
    if consensus.risk_flags:
        st.warning("**Risk Flags:**")
        for flag in consensus.risk_flags:
            st.markdown(f"- {flag}")

    # ---------------------------------------------------------------------------
    # Agent score cards
    # ---------------------------------------------------------------------------
    st.divider()
    st.subheader("Agent Scores Overview")

    evaluations = consensus.evaluations
    cols_per_row = 4
    for i in range(0, len(evaluations), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(evaluations):
                break
            ev = evaluations[idx]

            score_val = ev.score
            color = "#22c55e" if score_val >= 70 else "#eab308" if score_val >= 50 else "#ef4444"

            with col:
                st.markdown(
                    f'<div style="background:rgba(30,41,59,0.6);border:1px solid #334155;'
                    f'border-radius:10px;padding:0.8rem;text-align:center;min-height:130px">'
                    f'<div style="font-size:0.8rem;font-weight:600;color:#94a3b8">{ev.persona}</div>'
                    f'<div style="font-size:0.85rem;font-weight:700;margin:0.2rem 0">{ev.agent_name}</div>'
                    f'<div style="font-size:1.5rem;font-weight:800;color:{color}">{score_val:.0f}</div>'
                    f'<div style="font-size:0.7rem;color:#64748b">{ev.recommendation}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ---------------------------------------------------------------------------
    # Detailed evaluations
    # ---------------------------------------------------------------------------
    st.divider()
    st.subheader("Detailed Evaluations")

    for ev in evaluations:
        with st.expander(f"{ev.agent_name} ({ev.persona}) — {ev.score:.0f}/100 {ev.grade} — {ev.recommendation}"):
            st.markdown(f"**Rationale:** {ev.rationale}")

            if ev.strengths:
                st.markdown("**Strengths:**")
                for s in ev.strengths:
                    st.markdown(f"- ✅ {s}")

            if ev.concerns:
                st.markdown("**Concerns:**")
                for c in ev.concerns:
                    st.markdown(f"- ⚠️ {c}")

            if ev.skill_gaps:
                st.markdown("**Skill Gaps:**")
                for g in ev.skill_gaps:
                    st.markdown(f"- ❌ {g}")

            if ev.key_questions:
                st.markdown("**Suggested Interview Questions:**")
                for q in ev.key_questions:
                    st.markdown(f"- 💬 {q}")

    # ---------------------------------------------------------------------------
    # Deliberation log
    # ---------------------------------------------------------------------------
    with st.expander("📜 Deliberation Log (3 rounds)"):
        for d in consensus.discussion:
            round_color = {1: "#38bdf8", 2: "#a78bfa", 3: "#22c55e"}.get(d.round_number, "#94a3b8")
            st.markdown(
                f'<div style="border-left:3px solid {round_color};padding-left:0.75rem;margin-bottom:0.5rem">'
                f'<span style="color:{round_color};font-weight:600">R{d.round_number}</span> '
                f'<span style="font-weight:600">{d.agent_name}:</span> '
                f'<span style="color:#94a3b8">{d.message}</span></div>',
                unsafe_allow_html=True,
            )

    # ---------------------------------------------------------------------------
    # Interview focus areas
    # ---------------------------------------------------------------------------
    if consensus.interview_focus_areas:
        st.divider()
        st.subheader("🎤 Top Interview Questions (from all agents)")
        for i, q in enumerate(consensus.interview_focus_areas, 1):
            st.markdown(f"{i}. {q}")

    # Summary
    st.divider()
    st.markdown(consensus.summary)
else:
    st.info("Click **Run All Agents** to evaluate this candidate with all 11 specialist agents.")

    # Show agent catalogue
    st.subheader("Available Agents")
    for info in AGENT_CATALOGUE:
        st.markdown(f"- **{info['name']}** ({info['persona']}) — weight: {info['weight']:.0%} — {info['group']}")
