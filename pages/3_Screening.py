"""
Page 3: Screening — Upload resumes, run scoring + verification + red flags.
"""
from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config
from resume_parser import parse_resume
from scorer import score_candidate, rank_candidates
from verifier import run_verification
from red_flags import detect_red_flags
from pipeline import add_candidate, Stage

st.header("🔬 Resume Screening")

if "jd_criteria" not in st.session_state:
    st.warning("⚠️ No JD loaded. Go to **JD Management** first.")
    st.stop()

jd = st.session_state["jd_criteria"]
st.info(f"Screening against: **{jd.title}** ({len(jd.required_skills)} required skills)")

# ---------------------------------------------------------------------------
# Upload resumes
# ---------------------------------------------------------------------------

uploaded_files = st.file_uploader(
    "Upload Resumes (PDF, DOCX, TXT)",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True,
    help="Upload multiple resumes at once for batch screening",
)

col_opts1, col_opts2 = st.columns(2)
with col_opts1:
    run_verification_flag = st.checkbox("Run background verification", value=False,
                                         help="Verify companies, certs, LinkedIn, identity (slower)")
with col_opts2:
    run_red_flags_flag = st.checkbox("Run red flag detection", value=True,
                                      help="Detect employment gaps, job hopping, title inflation")

# ---------------------------------------------------------------------------
# Run screening
# ---------------------------------------------------------------------------

if st.button("🚀 Screen All Resumes", type="primary", use_container_width=True, disabled=not uploaded_files):
    cfg = load_config()
    tmp_dir = Path(__file__).resolve().parent.parent / "data" / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    # Progress bar
    progress = st.progress(0, text="Starting screening pipeline...")
    total_steps = len(uploaded_files) * (3 if run_verification_flag else 2) + 1
    step = 0

    candidates = []
    scores = []
    red_flag_reports = {}
    verifications = {}

    for i, f in enumerate(uploaded_files):
        # Save temp file
        tmp_path = tmp_dir / f.name
        tmp_path.write_bytes(f.read())

        # Parse
        step += 1
        progress.progress(step / total_steps, text=f"Parsing {f.name}...")
        try:
            candidate = parse_resume(str(tmp_path), cfg)
            candidates.append(candidate)

            # Add to pipeline
            pid = add_candidate(
                name=candidate.name,
                email=candidate.email,
                source_file=f.name,
                stage=Stage.PARSED,
            )
            st.session_state.setdefault("pipeline_ids", {})[candidate.name] = pid

        except Exception as e:
            st.error(f"Failed to parse {f.name}: {e}")
            continue

        # Verify (optional)
        if run_verification_flag:
            step += 1
            progress.progress(step / total_steps, text=f"Verifying {candidate.name}...")
            try:
                verifications[candidate.name] = run_verification(candidate, cfg)
            except Exception as e:
                st.warning(f"Verification error for {candidate.name}: {e}")

        # Score
        step += 1
        progress.progress(step / total_steps, text=f"Scoring {candidate.name}...")
        ver = verifications.get(candidate.name)
        score = score_candidate(candidate, jd, ver, cfg)
        scores.append(score)

        # Red flags
        if run_red_flags_flag:
            rf = detect_red_flags(candidate, jd)
            red_flag_reports[candidate.name] = rf

        # Update pipeline
        pid = st.session_state.get("pipeline_ids", {}).get(candidate.name)
        if pid:
            try:
                from pipeline import update_score, transition as pipe_transition
                update_score(pid, score.overall_score, score.grade)
                pipe_transition(pid, Stage.SCORED)
            except Exception:
                pass

    # Rank
    ranked = rank_candidates(scores)

    # Store in session
    st.session_state["scored_candidates"] = ranked
    st.session_state["red_flag_reports"] = red_flag_reports
    st.session_state["parsed_candidates"] = candidates

    progress.progress(1.0, text="✅ Screening complete!")

    st.success(f"Screened {len(ranked)} candidate(s)")

    # Quick preview
    st.divider()
    st.subheader("Quick Results")

    for s in ranked[:5]:
        grade_colors = {
            "A+": "🟢", "A": "🟢", "B+": "🔵", "B": "🔵",
            "C": "🟡", "D": "🟠", "F": "🔴",
        }
        icon = grade_colors.get(s.grade, "⚪")
        rf = red_flag_reports.get(s.candidate.name)
        rf_label = ""
        if rf and rf.total_flags > 0:
            rf_label = f"  |  ⚠️ {rf.total_flags} flag(s)"

        with st.container():
            col1, col2, col3, col4, col5 = st.columns([1, 4, 2, 2, 2])
            with col1:
                st.markdown(f"### #{s.rank}")
            with col2:
                st.markdown(f"**{s.candidate.name}**")
                st.caption(f"{s.candidate.total_experience_years:.1f} yrs experience")
            with col3:
                st.markdown(f"{icon} **{s.overall_score:.1f}** ({s.grade})")
            with col4:
                req_total = len(s.matched_required_skills) + len(s.missing_required_skills)
                st.markdown(f"Skills: {len(s.matched_required_skills)}/{req_total}")
            with col5:
                st.markdown(f"Trust: {s.verification.overall_trust_score:.0%}{rf_label}")

    st.info("Go to **Results & Rankings** for full details, or **Comparison Matrix** for side-by-side analysis.")
