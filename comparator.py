"""
comparator.py  –  Multi-Candidate Comparison Engine.

Generates side-by-side comparison matrices, radar charts data,
and gap analysis across multiple candidates.

Inspired by Career-Ops' 10-dimension weighted comparison,
adapted for the recruiter perspective.

Comparison dimensions:
  1. Skills Match       (25%)  — required + preferred skills coverage
  2. Experience Fit     (20%)  — years + relevance to JD
  3. Verification Trust (15%)  — overall trust score from all verifiers
  4. Red Flag Risk      (10%)  — inverse of red flag severity
  5. Education Match    (10%)  — degree level alignment
  6. Certification Fit  (5%)   — required + preferred cert coverage
  7. Semantic Relevance (5%)   — NLP similarity score
  8. Career Trajectory  (5%)   — growth pattern (title progression)
  9. Diversity of Exp   (5%)   — breadth of companies/industries
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from models import CandidateScore, JDCriteria


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class DimensionScore:
    name: str
    weight: float         # 0–1
    raw_score: float      # 0–100
    weighted_score: float # raw * weight
    detail: str


@dataclass
class CandidateComparison:
    name: str
    overall_composite: float      # 0–100 weighted across all dimensions
    grade: str
    dimensions: list[DimensionScore]
    strengths: list[str]          # Top 3 dimensions
    weaknesses: list[str]         # Bottom 3 dimensions
    radar_data: dict[str, float]  # dimension_name → 0-100 (for radar chart)


@dataclass
class ComparisonMatrix:
    jd_title: str
    candidates: list[CandidateComparison]
    dimension_names: list[str]
    best_per_dimension: dict[str, str]    # dimension → candidate name
    overall_recommendation: str
    stack_rank: list[str]                  # ordered candidate names


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

_DIMENSION_WEIGHTS = {
    "Skills Match": 0.25,
    "Experience Fit": 0.20,
    "Verification Trust": 0.15,
    "Red Flag Risk": 0.10,
    "Education Match": 0.10,
    "Certification Fit": 0.05,
    "Semantic Relevance": 0.05,
    "Career Trajectory": 0.05,
    "Experience Breadth": 0.05,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_candidates(
    scores: list[CandidateScore],
    jd: JDCriteria,
    red_flag_reports: dict[str, "RedFlagReport"] | None = None,
) -> ComparisonMatrix:
    """Generate a full comparison matrix across all dimensions."""
    candidates = []

    for s in scores:
        rf = red_flag_reports.get(s.candidate.name) if red_flag_reports else None
        dims = _compute_dimensions(s, jd, rf)

        composite = sum(d.weighted_score for d in dims)
        grade = _grade(composite)

        # Sort dimensions by raw score for strengths/weaknesses
        sorted_dims = sorted(dims, key=lambda d: d.raw_score, reverse=True)
        strengths = [f"{d.name} ({d.raw_score:.0f})" for d in sorted_dims[:3] if d.raw_score >= 60]
        weaknesses = [f"{d.name} ({d.raw_score:.0f})" for d in sorted_dims[-3:] if d.raw_score < 60]

        radar = {d.name: d.raw_score for d in dims}

        candidates.append(CandidateComparison(
            name=s.candidate.name,
            overall_composite=round(composite, 1),
            grade=grade,
            dimensions=dims,
            strengths=strengths,
            weaknesses=weaknesses,
            radar_data=radar,
        ))

    # Sort by composite
    candidates.sort(key=lambda c: c.overall_composite, reverse=True)
    stack_rank = [c.name for c in candidates]

    # Best per dimension
    dim_names = list(_DIMENSION_WEIGHTS.keys())
    best_per = {}
    for dname in dim_names:
        best_cand = max(candidates, key=lambda c: c.radar_data.get(dname, 0))
        best_per[dname] = best_cand.name

    # Recommendation
    recommendation = _build_recommendation(candidates, jd)

    return ComparisonMatrix(
        jd_title=jd.title,
        candidates=candidates,
        dimension_names=dim_names,
        best_per_dimension=best_per,
        overall_recommendation=recommendation,
        stack_rank=stack_rank,
    )


# ---------------------------------------------------------------------------
# Dimension computation
# ---------------------------------------------------------------------------

def _compute_dimensions(
    s: CandidateScore,
    jd: JDCriteria,
    rf_report: Optional["RedFlagReport"] = None,
) -> list[DimensionScore]:
    """Compute all dimension scores for one candidate."""
    dims = []

    # 1. Skills Match (25%)
    req_total = len(s.matched_required_skills) + len(s.missing_required_skills)
    pref_total = len(s.matched_preferred_skills) + len(jd.preferred_skills) - len(s.matched_preferred_skills)
    req_pct = len(s.matched_required_skills) / max(req_total, 1) * 100
    pref_pct = len(s.matched_preferred_skills) / max(pref_total, 1) * 100
    skills_raw = req_pct * 0.7 + pref_pct * 0.3
    w = _DIMENSION_WEIGHTS["Skills Match"]
    dims.append(DimensionScore(
        name="Skills Match", weight=w,
        raw_score=round(skills_raw, 1),
        weighted_score=round(skills_raw * w, 2),
        detail=f"{len(s.matched_required_skills)}/{req_total} required, {len(s.matched_preferred_skills)} preferred",
    ))

    # 2. Experience Fit (20%)
    exp_raw = _experience_fit(s, jd)
    w = _DIMENSION_WEIGHTS["Experience Fit"]
    dims.append(DimensionScore(
        name="Experience Fit", weight=w,
        raw_score=round(exp_raw, 1),
        weighted_score=round(exp_raw * w, 2),
        detail=f"{s.candidate.total_experience_years:.1f} yrs (need {jd.min_experience_years}-{jd.max_experience_years})",
    ))

    # 3. Verification Trust (15%)
    trust_raw = s.verification.overall_trust_score * 100
    w = _DIMENSION_WEIGHTS["Verification Trust"]
    dims.append(DimensionScore(
        name="Verification Trust", weight=w,
        raw_score=round(trust_raw, 1),
        weighted_score=round(trust_raw * w, 2),
        detail=f"Trust: {s.verification.overall_trust_score:.0%}",
    ))

    # 4. Red Flag Risk (10%) — inverse: 100 = no risk, 0 = high risk
    risk_raw = 100.0
    risk_detail = "No red flag data"
    if rf_report:
        risk_raw = max(0, (1.0 - rf_report.risk_score) * 100)
        risk_detail = f"{rf_report.total_flags} flags ({rf_report.risk_level})"
    w = _DIMENSION_WEIGHTS["Red Flag Risk"]
    dims.append(DimensionScore(
        name="Red Flag Risk", weight=w,
        raw_score=round(risk_raw, 1),
        weighted_score=round(risk_raw * w, 2),
        detail=risk_detail,
    ))

    # 5. Education Match (10%)
    edu_raw = s.breakdown.education / 10 * 100  # 10 is the max
    w = _DIMENSION_WEIGHTS["Education Match"]
    dims.append(DimensionScore(
        name="Education Match", weight=w,
        raw_score=round(edu_raw, 1),
        weighted_score=round(edu_raw * w, 2),
        detail=f"Education score: {s.breakdown.education:.1f}/10",
    ))

    # 6. Certification Fit (5%)
    cert_raw = s.breakdown.certifications / 10 * 100
    w = _DIMENSION_WEIGHTS["Certification Fit"]
    dims.append(DimensionScore(
        name="Certification Fit", weight=w,
        raw_score=round(cert_raw, 1),
        weighted_score=round(cert_raw * w, 2),
        detail=f"Cert score: {s.breakdown.certifications:.1f}/10",
    ))

    # 7. Semantic Relevance (5%)
    sem_raw = s.breakdown.semantic_similarity / 5 * 100
    w = _DIMENSION_WEIGHTS["Semantic Relevance"]
    dims.append(DimensionScore(
        name="Semantic Relevance", weight=w,
        raw_score=round(sem_raw, 1),
        weighted_score=round(sem_raw * w, 2),
        detail=f"Semantic: {s.breakdown.semantic_similarity:.1f}/5",
    ))

    # 8. Career Trajectory (5%)
    traj_raw = _career_trajectory(s)
    w = _DIMENSION_WEIGHTS["Career Trajectory"]
    dims.append(DimensionScore(
        name="Career Trajectory", weight=w,
        raw_score=round(traj_raw, 1),
        weighted_score=round(traj_raw * w, 2),
        detail=f"Trajectory score: {traj_raw:.0f}/100",
    ))

    # 9. Experience Breadth (5%)
    breadth_raw = _experience_breadth(s)
    w = _DIMENSION_WEIGHTS["Experience Breadth"]
    dims.append(DimensionScore(
        name="Experience Breadth", weight=w,
        raw_score=round(breadth_raw, 1),
        weighted_score=round(breadth_raw * w, 2),
        detail=f"Breadth: {breadth_raw:.0f}/100",
    ))

    return dims


def _experience_fit(s: CandidateScore, jd: JDCriteria) -> float:
    """Score how well experience years match the JD range."""
    actual = s.candidate.total_experience_years
    min_req = jd.min_experience_years
    max_req = jd.max_experience_years or min_req + 5  # default 5yr range

    if min_req == 0:
        return 100.0

    if min_req <= actual <= max_req:
        return 100.0

    if actual < min_req:
        return max(0, (actual / min_req) * 80)

    # Over-qualified
    overshoot = actual - max_req
    return max(40, 100 - overshoot * 5)


def _career_trajectory(s: CandidateScore) -> float:
    """Assess career growth pattern from title progression."""
    title_levels = {
        "intern": 0, "junior": 1, "associate": 2, "mid": 3,
        "senior": 4, "staff": 5, "lead": 6, "principal": 7,
        "director": 8, "vp": 9, "cto": 10, "head": 8,
        "manager": 6, "architect": 7,
    }

    exps = s.candidate.experience
    if len(exps) < 2:
        return 60.0  # Neutral — not enough data

    levels = []
    for exp in exps:
        title_lower = exp.title.lower()
        best_level = 3  # default mid
        for keyword, level in title_levels.items():
            if keyword in title_lower:
                best_level = max(best_level, level)
        levels.append(best_level)

    # Check if trajectory is upward
    if len(levels) >= 2:
        # Compare first half vs second half
        mid = len(levels) // 2
        avg_early = sum(levels[:mid]) / max(mid, 1)
        avg_late = sum(levels[mid:]) / max(len(levels) - mid, 1)

        if avg_late > avg_early:
            return min(100, 70 + (avg_late - avg_early) * 10)
        elif avg_late == avg_early:
            return 60.0  # Flat
        else:
            return max(20, 60 - (avg_early - avg_late) * 10)  # Declining

    return 50.0


def _experience_breadth(s: CandidateScore) -> float:
    """Score diversity of experience (companies, variety)."""
    companies = {e.company.lower().strip() for e in s.candidate.experience if e.company}
    unique = len(companies)

    if unique >= 5:
        return 90.0
    elif unique >= 3:
        return 70.0
    elif unique >= 2:
        return 50.0
    elif unique == 1:
        return 30.0  # All experience at one company
    return 10.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _grade(score: float) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B+"
    if score >= 60: return "B"
    if score >= 50: return "C"
    if score >= 40: return "D"
    return "F"


def _build_recommendation(candidates: list[CandidateComparison], jd: JDCriteria) -> str:
    """Generate a recommendation based on the comparison."""
    if not candidates:
        return "No candidates to compare."

    top = candidates[0]
    if top.overall_composite >= 80:
        return (
            f"Strong recommendation: {top.name} ({top.overall_composite:.0f}/100, {top.grade}) "
            f"is a clear frontrunner. Proceed to interview."
        )
    elif top.overall_composite >= 60 and len(candidates) > 1:
        second = candidates[1]
        gap = top.overall_composite - second.overall_composite
        if gap < 5:
            return (
                f"Close competition between {top.name} ({top.overall_composite:.0f}) "
                f"and {second.name} ({second.overall_composite:.0f}). "
                f"Interview both to differentiate."
            )
        return (
            f"Moderate match: {top.name} leads at {top.overall_composite:.0f}/100. "
            f"Consider interviewing top 2-3 candidates."
        )
    else:
        return (
            f"Weak candidate pool. Best candidate {top.name} scores "
            f"{top.overall_composite:.0f}/100. Consider revising JD or expanding search."
        )
