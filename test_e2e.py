#!/usr/bin/env python3
"""E2E test for the full pipeline with agents, history, and interview gen."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from jd_analyzer import analyze_jd
from resume_parser import parse_resume
from scorer import score_candidate, rank_candidates, compute_skill_gap
from agents import evaluate_candidate
from history import save_session, get_all_sessions, get_stats_summary
from interview_gen import generate_questionnaire

cfg = load_config()

print("1. Parsing JD...")
jd = analyze_jd("data/jds/2026-Public Cloud Senior Consultant AWS USA-reviewed (1).docx", cfg)
print(f"   JD: {jd.title} | {len(jd.required_skills)} req skills | {jd.role_level}")

print("2. Parsing resumes...")
resumes = [
    "data/Naukri_KalyanC[9y_0m].docx",
    "data/Naukri_GauravKumar[9y_0m] (1).docx",
]
candidates = []
for r in resumes:
    try:
        c = parse_resume(r, cfg)
        candidates.append(c)
        print(f"   Parsed: {c.name}")
    except Exception as e:
        print(f"   Failed: {r}: {e}")

print("3. Scoring...")
scores = []
for c in candidates:
    s = score_candidate(c, jd, None, cfg)
    scores.append(s)
    print(f"   {c.name}: {s.overall_score}/100 ({s.grade})")

ranked = rank_candidates(scores)

print("4. Agent Panel Evaluation...")
agent_results = {}
for s in ranked:
    consensus = evaluate_candidate(s.candidate, jd, s, s.verification)
    agent_results[s.candidate.name] = consensus
    print(f"   {s.candidate.name}: consensus={consensus.consensus_score}/100 ({consensus.consensus_grade})")
    print(f"     Recommendation: {consensus.consensus_recommendation}, Confidence: {consensus.confidence:.0%}")
    for ev in consensus.evaluations:
        print(f"     {ev.agent_name}: {ev.score}/100 -> {ev.recommendation}")
    if consensus.risk_flags:
        print(f"     Risk flags: {consensus.risk_flags}")

print("5. Skill Gap Analysis...")
for s in ranked:
    gap = compute_skill_gap(s.candidate.skills, s.candidate.raw_text, jd)
    print(f"   {s.candidate.name}: {gap['required_match_pct']}% req match, severity={gap['gap_severity']}")
    if gap["critical_gaps"]:
        print(f"     Critical gaps: {gap['critical_gaps'][:3]}")

print("6. Interview Questionnaire...")
for s in ranked:
    consensus = agent_results.get(s.candidate.name)
    q = generate_questionnaire(s.candidate, jd, s, consensus)
    print(f"   {s.candidate.name}: {q.total_questions} questions across {len(q.sections)} sections")
    for sec, qs in q.sections.items():
        print(f"     {sec}: {len(qs)} questions")

print("7. Saving to history...")
session_id = save_session(jd, ranked, agent_results)
print(f"   Saved session #{session_id}")

sessions = get_all_sessions()
print(f"   Total sessions: {len(sessions)}")

stats = get_stats_summary()
print(f"   Total candidates scanned: {stats['total_candidates']}")
print(f"   Grade distribution: {stats['grade_distribution']}")

print()
print("=" * 60)
print("FULL END-TO-END PIPELINE PASSED!")
print("=" * 60)
