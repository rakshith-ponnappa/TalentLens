"""
jd_quality.py  –  Job Description Quality Analyzer.

Evaluates the JD itself before using it to screen candidates.
Helps recruiters write better JDs and flags problematic postings.

Dimensions scored (each 0–100):
  1. Clarity        – Are requirements specific and unambiguous?
  2. Completeness   – Does it cover skills, experience, education, comp?
  3. Realism        – Are expectations achievable (not a "unicorn" JD)?
  4. Inclusivity    – Free of biased/exclusionary language?
  5. Attractiveness – Does it sell the role (benefits, growth, culture)?

Overall JD Quality Score = weighted average → A+ to F grade.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from models import JDCriteria


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class QualityDimension:
    name: str
    score: float          # 0–100
    weight: float         # 0–1 (weights sum to 1.0)
    issues: list[str]     # Problems found
    suggestions: list[str]  # How to improve


@dataclass
class JDQualityReport:
    overall_score: float   # 0–100
    grade: str             # A+ through F
    dimensions: list[QualityDimension]
    red_flags: list[str]   # Serious problems
    strengths: list[str]   # What's done well
    summary: str
    word_count: int
    estimated_read_time_min: float


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "Clarity": 0.25,
    "Completeness": 0.25,
    "Realism": 0.20,
    "Inclusivity": 0.15,
    "Attractiveness": 0.15,
}


# ---------------------------------------------------------------------------
# Known patterns
# ---------------------------------------------------------------------------

_VAGUE_REQUIREMENTS = [
    r"\bexcellent communication\b",
    r"\bself[- ]?starter\b",
    r"\bfast[- ]?paced\b",
    r"\bteam player\b",
    r"\bgo[- ]?getter\b",
    r"\brock\s?star\b",
    r"\bninja\b",
    r"\bguru\b",
    r"\bwear many hats\b",
    r"\bhustler\b",
    r"\bpassionate\b",
    r"\bhighly motivated\b",
    r"\bdetail[- ]?oriented\b",
]

_BIASED_TERMS = [
    (r"\byoung\b", "Consider 'early-career' instead of age-specific language"),
    (r"\bhe\s", "Use gender-neutral pronouns (they/the candidate)"),
    (r"\bhis\s", "Use gender-neutral pronouns"),
    (r"\bnative\s+(?:english|speaker)\b", "Use 'fluent' or 'proficient' instead of 'native'"),
    (r"\bcultural\s+fit\b", "Use 'values alignment' — 'cultural fit' can mask bias"),
    (r"\bdigital\s+native\b", "Implies age discrimination — describe specific skills needed"),
    (r"\bman\s*(?:power|hours)\b", "Use 'person-hours' or 'effort'"),
    (r"\bmaster\s*/\s*slave\b", "Use 'primary/secondary' or 'leader/follower'"),
    (r"\bgrandfathered\b", "Use 'legacy' or 'pre-existing'"),
]

_COMPENSATION_PATTERNS = [
    r"\$[\d,]+",
    r"salary",
    r"compensation",
    r"pay\s+range",
    r"benefits",
    r"equity",
    r"stock\s+options",
    r"bonus",
    r"OTE",
    r"total\s+comp",
]

_GROWTH_PATTERNS = [
    r"career\s+(growth|path|development|progression)",
    r"learning\s+(opportunities|budget)",
    r"mentorship",
    r"promotion",
    r"training",
    r"conference",
    r"professional\s+development",
]

_CULTURE_PATTERNS = [
    r"remote",
    r"hybrid",
    r"work[- ]life\s+balance",
    r"flexible",
    r"pto",
    r"vacation",
    r"parental\s+leave",
    r"wellness",
    r"inclusive",
    r"diversity",
    r"health\s+insurance",
    r"401k",
    r"pension",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_jd_quality(jd: JDCriteria) -> JDQualityReport:
    """Analyze a parsed JD for quality across all dimensions."""
    text = jd.raw_text
    text_lower = text.lower()
    word_count = len(text.split())

    dimensions = [
        _score_clarity(jd, text_lower, word_count),
        _score_completeness(jd, text_lower),
        _score_realism(jd, text_lower),
        _score_inclusivity(text, text_lower),
        _score_attractiveness(jd, text_lower),
    ]

    overall = sum(d.score * d.weight for d in dimensions)
    grade = _grade(overall)

    red_flags = []
    strengths = []

    for d in dimensions:
        if d.score < 40:
            red_flags.append(f"{d.name}: {d.issues[0]}" if d.issues else f"{d.name} score critically low")
        elif d.score >= 80:
            strengths.append(f"{d.name}: Well-crafted" + (f" — {d.suggestions[0]}" if d.suggestions else ""))

    # Global red flags
    if word_count < 100:
        red_flags.append("JD is extremely short — likely missing critical information")
    if word_count > 2000:
        red_flags.append("JD is very long — candidates may not read it fully")
    if len(jd.required_skills) > 20:
        red_flags.append(f"Too many required skills ({len(jd.required_skills)}) — unrealistic expectations")

    summary = _build_summary(grade, overall, red_flags, strengths)

    return JDQualityReport(
        overall_score=round(overall, 1),
        grade=grade,
        dimensions=dimensions,
        red_flags=red_flags,
        strengths=strengths,
        summary=summary,
        word_count=word_count,
        estimated_read_time_min=round(word_count / 250, 1),
    )


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------

def _score_clarity(jd: JDCriteria, text: str, word_count: int) -> QualityDimension:
    """Are requirements specific and unambiguous?"""
    score = 100.0
    issues = []
    suggestions = []

    # Check for vague requirements
    vague_found = []
    for pattern in _VAGUE_REQUIREMENTS:
        if re.search(pattern, text, re.IGNORECASE):
            vague_found.append(re.search(pattern, text, re.IGNORECASE).group())

    if vague_found:
        deduction = min(30, len(vague_found) * 8)
        score -= deduction
        issues.append(f"Vague buzzwords: {', '.join(vague_found[:5])}")
        suggestions.append("Replace buzzwords with specific, measurable requirements")

    # Skills specificity — very short skill names are vague
    vague_skills = [s for s in jd.required_skills if len(s) < 3]
    if vague_skills:
        score -= len(vague_skills) * 5
        issues.append(f"Ambiguous skill names: {', '.join(vague_skills)}")

    # Experience range clarity
    if jd.min_experience_years > 0 and jd.max_experience_years == 0:
        score -= 10
        suggestions.append("Add a max experience range to avoid over-qualified applicants")

    # Word count penalties
    if word_count < 150:
        score -= 20
        issues.append("JD too brief — lacks enough detail for candidates to self-assess")
    elif word_count > 1500:
        score -= 10
        suggestions.append("Consider condensing — long JDs discourage applicants")

    # No clear role level
    if jd.role_level.lower() in ("", "any", "unknown"):
        score -= 10
        issues.append("No clear seniority level specified")

    return QualityDimension(
        name="Clarity", score=max(0, score), weight=_WEIGHTS["Clarity"],
        issues=issues, suggestions=suggestions,
    )


def _score_completeness(jd: JDCriteria, text: str) -> QualityDimension:
    """Does it cover all essential sections?"""
    score = 0.0
    issues = []
    suggestions = []

    # Required sections check (each worth points)
    checks = [
        (bool(jd.required_skills), 20, "Required skills specified"),
        (bool(jd.preferred_skills), 10, "Preferred skills specified"),
        (jd.min_experience_years > 0, 15, "Experience requirements"),
        (jd.education_level.lower() not in ("", "any"), 10, "Education requirements"),
        (bool(jd.title), 10, "Clear job title"),
        (bool(jd.industry), 5, "Industry context"),
        (bool(jd.role_level) and jd.role_level.lower() != "any", 10, "Seniority level"),
    ]

    for present, points, label in checks:
        if present:
            score += points
        else:
            issues.append(f"Missing: {label}")
            suggestions.append(f"Add {label.lower()}")

    # Compensation mention
    has_comp = any(re.search(p, text, re.IGNORECASE) for p in _COMPENSATION_PATTERNS)
    if has_comp:
        score += 15
    else:
        issues.append("No salary/compensation information")
        suggestions.append("Including salary range increases application quality by 30%+")

    # Responsibilities vs requirements
    has_responsibilities = any(kw in text for kw in [
        "responsibilit", "you will", "your role", "what you'll do", "duties",
    ])
    if has_responsibilities:
        score += 5
    else:
        suggestions.append("Add a 'Responsibilities' section")

    return QualityDimension(
        name="Completeness", score=min(100, score), weight=_WEIGHTS["Completeness"],
        issues=issues, suggestions=suggestions,
    )


def _score_realism(jd: JDCriteria, text: str) -> QualityDimension:
    """Are expectations achievable?"""
    score = 100.0
    issues = []
    suggestions = []

    # Too many required skills (unicorn JD)
    req_count = len(jd.required_skills)
    if req_count > 20:
        score -= 35
        issues.append(f"{req_count} required skills — 'unicorn' JD that will filter out all candidates")
        suggestions.append("Reduce required skills to 8-12 core competencies; move rest to preferred")
    elif req_count > 15:
        score -= 20
        issues.append(f"{req_count} required skills is above average")
        suggestions.append("Consider moving 5+ to preferred skills")
    elif req_count > 10:
        score -= 5

    # Experience range too wide or too narrow
    exp_range = jd.max_experience_years - jd.min_experience_years
    if jd.max_experience_years > 0:
        if exp_range > 10:
            score -= 15
            issues.append(f"Experience range too wide: {jd.min_experience_years}-{jd.max_experience_years} years")
            suggestions.append("Narrow the range to 3-5 years to attract the right level")
        elif exp_range < 1 and jd.min_experience_years > 2:
            score -= 10
            issues.append("Very narrow experience range may exclude strong candidates")

    # Junior role with senior requirements
    if jd.role_level.lower() in ("junior", "entry") and jd.min_experience_years > 3:
        score -= 25
        issues.append(f"Junior/entry role requiring {jd.min_experience_years}+ years")
        suggestions.append("Mismatch between role level and experience — adjust one")

    # Senior role with too few requirements
    if jd.role_level.lower() in ("lead", "principal") and req_count < 5:
        score -= 10
        suggestions.append("Senior/lead roles should specify deeper technical requirements")

    # Contradictory signals: entry-level + expert certifications
    expert_certs = [c for c in jd.certifications_required if any(
        kw in c.lower() for kw in ["professional", "expert", "architect", "specialty"]
    )]
    if jd.role_level.lower() in ("junior", "entry") and expert_certs:
        score -= 15
        issues.append(f"Entry role requiring expert certifications: {', '.join(expert_certs)}")

    return QualityDimension(
        name="Realism", score=max(0, score), weight=_WEIGHTS["Realism"],
        issues=issues, suggestions=suggestions,
    )


def _score_inclusivity(text: str, text_lower: str) -> QualityDimension:
    """Free of biased or exclusionary language?"""
    score = 100.0
    issues = []
    suggestions = []

    for pattern, suggestion in _BIASED_TERMS:
        if re.search(pattern, text_lower):
            match = re.search(pattern, text_lower).group()
            score -= 15
            issues.append(f"Potentially biased: '{match}'")
            suggestions.append(suggestion)

    # Positive signals (add points back)
    inclusive_signals = [
        r"equal\s+opportunity",
        r"diverse\s+candidates",
        r"regardless\s+of",
        r"accommodation",
        r"accessible",
    ]
    for pattern in inclusive_signals:
        if re.search(pattern, text_lower):
            score = min(100, score + 5)

    return QualityDimension(
        name="Inclusivity", score=max(0, score), weight=_WEIGHTS["Inclusivity"],
        issues=issues, suggestions=suggestions,
    )


def _score_attractiveness(jd: JDCriteria, text: str) -> QualityDimension:
    """Does it sell the role?"""
    score = 30.0  # Start low — must earn points
    issues = []
    suggestions = []

    # Compensation transparency
    has_comp = any(re.search(p, text, re.IGNORECASE) for p in _COMPENSATION_PATTERNS)
    if has_comp:
        score += 25
    else:
        suggestions.append("Add salary range — it's the #1 factor candidates look for")

    # Growth opportunities
    growth_matches = sum(1 for p in _GROWTH_PATTERNS if re.search(p, text, re.IGNORECASE))
    if growth_matches >= 2:
        score += 20
    elif growth_matches == 1:
        score += 10
    else:
        suggestions.append("Mention career growth, learning budget, or mentorship opportunities")

    # Culture/benefits
    culture_matches = sum(1 for p in _CULTURE_PATTERNS if re.search(p, text, re.IGNORECASE))
    if culture_matches >= 3:
        score += 25
    elif culture_matches >= 1:
        score += 15
    else:
        suggestions.append("Add benefits/culture details (remote policy, PTO, insurance)")

    # Company description
    has_company = any(kw in text for kw in [
        "about us", "who we are", "our mission", "our company",
        "about the company", "what we do",
    ])
    if has_company:
        score += 10
    else:
        suggestions.append("Add a brief company description")

    if not issues and score >= 80:
        issues = []
    elif score < 50:
        issues.append("JD reads as a requirements list — doesn't sell the opportunity")

    return QualityDimension(
        name="Attractiveness", score=min(100, score), weight=_WEIGHTS["Attractiveness"],
        issues=issues, suggestions=suggestions,
    )


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


def _build_summary(grade: str, score: float, red_flags: list[str], strengths: list[str]) -> str:
    parts = [f"JD Quality: {grade} ({score:.0f}/100)"]
    if strengths:
        parts.append(f"Strengths: {', '.join(strengths[:3])}")
    if red_flags:
        parts.append(f"Issues: {', '.join(red_flags[:3])}")
    return ". ".join(parts) + "."
