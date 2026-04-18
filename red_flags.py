"""
red_flags.py  –  Candidate Red Flag Detection Engine.

Analyses candidate profiles for warning signals that warrant deeper scrutiny:
  - Employment gaps (>6 months unexplained)
  - Job hopping (avg tenure < 18 months over 3+ roles)
  - Title inflation (senior titles with insufficient experience)
  - Skill inconsistencies (claims vs evidence in resume text)
  - Education red flags (unaccredited, diploma mills, mismatched dates)
  - Experience timeline anomalies (overlaps, impossibilities)
  - Geographic inconsistencies
  - Disposable email addresses

Each flag has a severity (critical / warning / info) and confidence score.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from models import CandidateProfile, JDCriteria


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

class Severity:
    CRITICAL = "critical"    # Likely disqualifying
    WARNING  = "warning"     # Needs investigation
    INFO     = "info"        # Notable but not blocking


@dataclass
class RedFlag:
    category: str            # "employment_gap", "job_hopping", etc.
    severity: str            # Severity.CRITICAL / WARNING / INFO
    title: str               # Short human-readable label
    detail: str              # Full explanation
    evidence: str            # What data triggered this
    confidence: float        # 0.0–1.0 how sure we are
    suggestion: str          # What the interviewer should ask/check


@dataclass
class RedFlagReport:
    candidate_name: str
    total_flags: int
    critical_count: int
    warning_count: int
    info_count: int
    risk_level: str          # "high" / "medium" / "low" / "clean"
    risk_score: float        # 0.0 (clean) – 1.0 (very risky)
    flags: list[RedFlag]
    summary: str


# ---------------------------------------------------------------------------
# Known patterns
# ---------------------------------------------------------------------------

_DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwaway.email",
    "yopmail.com", "sharklasers.com", "guerrillamailblock.com", "grr.la",
    "dispostable.com", "maildrop.cc", "10minutemail.com", "trashmail.com",
    "temp-mail.org", "fakeinbox.com", "getnada.com", "emailondeck.com",
    "burnermail.io", "mohmal.com", "discard.email",
}

_DIPLOMA_MILL_KEYWORDS = {
    "life experience", "accreditation mill", "unaccredited",
    "buy degree", "instant degree", "no study required",
}

_INFLATED_TITLE_PATTERNS = {
    # Title → minimum years typically expected
    "cto": 15, "vp": 12, "vice president": 12, "director": 10,
    "principal": 10, "staff": 8, "senior": 4, "lead": 5,
    "head of": 10, "chief": 15, "architect": 6,
}

_STOPWORD_COMPANIES = {
    "freelance", "self-employed", "self employed", "consultant",
    "independent", "personal", "various", "multiple",
    "confidential", "nda", "undisclosed",
}


# ---------------------------------------------------------------------------
# Detection functions
# ---------------------------------------------------------------------------

def detect_red_flags(
    candidate: CandidateProfile,
    jd: JDCriteria | None = None,
) -> RedFlagReport:
    """Run all red flag detectors on a candidate. Returns a full report."""
    flags: list[RedFlag] = []

    flags.extend(_check_employment_gaps(candidate))
    flags.extend(_check_job_hopping(candidate))
    flags.extend(_check_title_inflation(candidate))
    flags.extend(_check_skill_inconsistencies(candidate, jd))
    flags.extend(_check_education_flags(candidate))
    flags.extend(_check_timeline_anomalies(candidate))
    flags.extend(_check_email_flags(candidate))
    flags.extend(_check_vague_descriptions(candidate))
    flags.extend(_check_geographic_inconsistencies(candidate))

    # Sort by severity (critical first)
    severity_order = {Severity.CRITICAL: 0, Severity.WARNING: 1, Severity.INFO: 2}
    flags.sort(key=lambda f: (severity_order.get(f.severity, 9), -f.confidence))

    critical = sum(1 for f in flags if f.severity == Severity.CRITICAL)
    warning = sum(1 for f in flags if f.severity == Severity.WARNING)
    info = sum(1 for f in flags if f.severity == Severity.INFO)

    # Risk score: critical=0.3 each, warning=0.1, info=0.02 (capped at 1.0)
    risk_score = min(1.0, critical * 0.3 + warning * 0.1 + info * 0.02)
    risk_level = (
        "high" if risk_score >= 0.6 else
        "medium" if risk_score >= 0.3 else
        "low" if risk_score > 0 else
        "clean"
    )

    summary = _build_summary(flags, risk_level, candidate.name)

    return RedFlagReport(
        candidate_name=candidate.name,
        total_flags=len(flags),
        critical_count=critical,
        warning_count=warning,
        info_count=info,
        risk_level=risk_level,
        risk_score=round(risk_score, 2),
        flags=flags,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Individual detectors
# ---------------------------------------------------------------------------

def _check_employment_gaps(candidate: CandidateProfile) -> list[RedFlag]:
    """Detect gaps > 6 months between consecutive roles."""
    flags = []
    exps = sorted(candidate.experience, key=lambda e: e.start_date or "")

    for i in range(len(exps) - 1):
        end_current = _parse_date(exps[i].end_date)
        start_next = _parse_date(exps[i + 1].start_date)

        if not end_current or not start_next:
            continue

        gap_months = (start_next.year - end_current.year) * 12 + (start_next.month - end_current.month)

        if gap_months > 12:
            flags.append(RedFlag(
                category="employment_gap",
                severity=Severity.WARNING,
                title=f"Employment gap: {gap_months} months",
                detail=(
                    f"Gap of ~{gap_months} months between "
                    f"{exps[i].company} ({exps[i].end_date}) and "
                    f"{exps[i + 1].company} ({exps[i + 1].start_date})"
                ),
                evidence=f"{exps[i].end_date} → {exps[i + 1].start_date}",
                confidence=0.85,
                suggestion="Ask about activities during this period (education, personal reasons, job search?)",
            ))
        elif gap_months > 6:
            flags.append(RedFlag(
                category="employment_gap",
                severity=Severity.INFO,
                title=f"Employment gap: {gap_months} months",
                detail=(
                    f"Gap of ~{gap_months} months between "
                    f"{exps[i].company} and {exps[i + 1].company}"
                ),
                evidence=f"{exps[i].end_date} → {exps[i + 1].start_date}",
                confidence=0.7,
                suggestion="Worth a brief question about the gap.",
            ))

    return flags


def _check_job_hopping(candidate: CandidateProfile) -> list[RedFlag]:
    """Detect patterns of very short tenures."""
    flags = []
    exps = [e for e in candidate.experience if e.duration_months > 0]

    if len(exps) < 3:
        return flags

    # Average tenure
    avg_months = sum(e.duration_months for e in exps) / len(exps)
    short_stints = [e for e in exps if e.duration_months < 12]

    if avg_months < 12 and len(short_stints) >= 3:
        flags.append(RedFlag(
            category="job_hopping",
            severity=Severity.WARNING,
            title=f"Frequent job changes (avg {avg_months:.0f} mo)",
            detail=(
                f"Average tenure of {avg_months:.0f} months across {len(exps)} roles. "
                f"{len(short_stints)} roles lasted under 12 months."
            ),
            evidence=", ".join(f"{e.company} ({e.duration_months}mo)" for e in short_stints[:5]),
            confidence=0.8,
            suggestion="Explore reasons for frequent moves — was it contracts, layoffs, or dissatisfaction?",
        ))
    elif avg_months < 18 and len(short_stints) >= 2:
        flags.append(RedFlag(
            category="job_hopping",
            severity=Severity.INFO,
            title=f"Below-average tenure (avg {avg_months:.0f} mo)",
            detail=f"Average tenure of {avg_months:.0f} months; {len(short_stints)} role(s) under a year.",
            evidence=", ".join(f"{e.company} ({e.duration_months}mo)" for e in short_stints[:3]),
            confidence=0.6,
            suggestion="Ask about career goals and what they look for in long-term roles.",
        ))

    # Descending tenure trend (getting shorter each time)
    if len(exps) >= 4:
        tenures = [e.duration_months for e in exps]
        decreasing = all(tenures[i] >= tenures[i + 1] for i in range(min(4, len(tenures)) - 1))
        if decreasing and tenures[-1] < 12:
            flags.append(RedFlag(
                category="job_hopping",
                severity=Severity.WARNING,
                title="Declining tenure trend",
                detail="Each successive role is shorter than the previous — pattern of decreasing engagement.",
                evidence=" → ".join(f"{t}mo" for t in tenures[:5]),
                confidence=0.65,
                suggestion="Probe what's driving the pattern — burnout, wrong fits, or something else?",
            ))

    return flags


def _check_title_inflation(candidate: CandidateProfile) -> list[RedFlag]:
    """Detect senior/leadership titles with suspiciously few years."""
    flags = []
    total_years = candidate.total_experience_years

    for exp in candidate.experience:
        title_lower = exp.title.lower()
        for pattern, min_years in _INFLATED_TITLE_PATTERNS.items():
            if pattern in title_lower and total_years < min_years * 0.6:
                flags.append(RedFlag(
                    category="title_inflation",
                    severity=Severity.WARNING,
                    title=f"Title vs experience mismatch",
                    detail=(
                        f'"{exp.title}" at {exp.company} with only '
                        f"{total_years:.1f} years total experience. "
                        f"Typically this title requires {min_years}+ years."
                    ),
                    evidence=f"{exp.title} @ {exp.company}, {total_years:.1f} yrs total",
                    confidence=0.7,
                    suggestion="Validate actual scope and team size for this role.",
                ))
                break  # One flag per experience entry

    return flags


def _check_skill_inconsistencies(
    candidate: CandidateProfile,
    jd: JDCriteria | None,
) -> list[RedFlag]:
    """Detect skills claimed but never evidenced in experience descriptions."""
    flags = []
    if not candidate.skills:
        return flags

    # Combine all experience descriptions
    exp_text = " ".join(e.description.lower() for e in candidate.experience if e.description)
    if not exp_text:
        return flags

    # Check top skills — are they mentioned in actual work descriptions?
    high_value_skills = set()
    if jd:
        high_value_skills = {s.lower() for s in jd.required_skills}

    unevidenced = []
    for skill in candidate.skills:
        skill_lower = skill.lower()
        if skill_lower in high_value_skills:
            # Check if this JD-required skill appears in work descriptions
            if skill_lower not in exp_text and len(skill_lower) > 2:
                unevidenced.append(skill)

    if len(unevidenced) >= 3:
        flags.append(RedFlag(
            category="skill_inconsistency",
            severity=Severity.INFO,
            title=f"{len(unevidenced)} key skills not evidenced in experience",
            detail=(
                "These JD-required skills are listed but don't appear in "
                "any work experience description: " + ", ".join(unevidenced[:8])
            ),
            evidence=", ".join(unevidenced[:8]),
            confidence=0.5,
            suggestion="Ask for specific examples of using these skills in real projects.",
        ))

    return flags


def _check_education_flags(candidate: CandidateProfile) -> list[RedFlag]:
    """Check for education-related red flags."""
    flags = []

    for edu in candidate.education:
        # Graduation year in the future
        if edu.graduation_year and edu.graduation_year > datetime.now().year:
            flags.append(RedFlag(
                category="education",
                severity=Severity.INFO,
                title="Future graduation date",
                detail=f"{edu.institution}: graduation year {edu.graduation_year} is in the future",
                evidence=f"{edu.degree} from {edu.institution}, {edu.graduation_year}",
                confidence=0.9,
                suggestion="Confirm if they're still a student and expected graduation.",
            ))

        # Very old graduation with no recent education
        if edu.graduation_year and edu.graduation_year < 1980:
            flags.append(RedFlag(
                category="education",
                severity=Severity.INFO,
                title="Very old graduation date",
                detail=f"Graduation year {edu.graduation_year} from {edu.institution}",
                evidence=str(edu.graduation_year),
                confidence=0.6,
                suggestion="May be a parsing error — verify.",
            ))

    return flags


def _check_timeline_anomalies(candidate: CandidateProfile) -> list[RedFlag]:
    """Detect overlapping employment, impossible timelines."""
    flags = []
    exps = candidate.experience

    # Check for overlaps
    for i in range(len(exps)):
        for j in range(i + 1, len(exps)):
            start_i = _parse_date(exps[i].start_date)
            end_i = _parse_date(exps[i].end_date)
            start_j = _parse_date(exps[j].start_date)
            end_j = _parse_date(exps[j].end_date)

            if not all([start_i, end_i, start_j, end_j]):
                continue

            # Check overlap
            if start_i <= end_j and start_j <= end_i:
                overlap_months = _overlap_months(start_i, end_i, start_j, end_j)
                if overlap_months > 3:
                    flags.append(RedFlag(
                        category="timeline_overlap",
                        severity=Severity.INFO if overlap_months < 6 else Severity.WARNING,
                        title=f"Overlapping roles ({overlap_months} mo)",
                        detail=(
                            f"{exps[i].title} at {exps[i].company} overlaps with "
                            f"{exps[j].title} at {exps[j].company} by ~{overlap_months} months"
                        ),
                        evidence=f"{exps[i].start_date}-{exps[i].end_date} vs {exps[j].start_date}-{exps[j].end_date}",
                        confidence=0.7,
                        suggestion="Could be legitimate (moonlighting/transition). Ask about it.",
                    ))

    # Total claimed vs calculated years mismatch
    if candidate.total_experience_years > 0:
        calculated = sum(e.duration_months for e in exps if e.duration_months > 0) / 12.0
        if calculated > 0 and abs(candidate.total_experience_years - calculated) > 3:
            flags.append(RedFlag(
                category="timeline_mismatch",
                severity=Severity.WARNING,
                title="Experience years mismatch",
                detail=(
                    f"Claims {candidate.total_experience_years:.1f} years total, "
                    f"but listed roles sum to ~{calculated:.1f} years"
                ),
                evidence=f"Claimed: {candidate.total_experience_years}, Calculated: {calculated:.1f}",
                confidence=0.75,
                suggestion="Ask about unlisted roles or the discrepancy.",
            ))

    return flags


def _check_email_flags(candidate: CandidateProfile) -> list[RedFlag]:
    """Check email for red flags."""
    flags = []
    email = candidate.email.lower().strip()

    if not email:
        flags.append(RedFlag(
            category="contact",
            severity=Severity.INFO,
            title="No email provided",
            detail="Resume does not contain an email address",
            evidence="",
            confidence=0.9,
            suggestion="Request contact information.",
        ))
        return flags

    domain = email.split("@")[-1] if "@" in email else ""

    if domain in _DISPOSABLE_DOMAINS:
        flags.append(RedFlag(
            category="contact",
            severity=Severity.CRITICAL,
            title="Disposable email address",
            detail=f"Email uses disposable provider: {domain}",
            evidence=email,
            confidence=0.95,
            suggestion="Request a permanent email. This is a strong indicator of a non-serious applicant.",
        ))

    return flags


def _check_vague_descriptions(candidate: CandidateProfile) -> list[RedFlag]:
    """Detect experience entries with vague/empty descriptions."""
    flags = []
    vague_entries = []

    for exp in candidate.experience:
        desc = (exp.description or "").strip()
        if len(desc) < 30 and exp.duration_months > 6:
            vague_entries.append(f"{exp.title} at {exp.company}")

    if len(vague_entries) >= 2:
        flags.append(RedFlag(
            category="vague_description",
            severity=Severity.INFO,
            title=f"{len(vague_entries)} roles lack detail",
            detail="Multiple roles have minimal or no description of responsibilities/achievements",
            evidence="; ".join(vague_entries[:4]),
            confidence=0.6,
            suggestion="Ask for specific accomplishments and metrics in these roles.",
        ))

    return flags


def _check_geographic_inconsistencies(candidate: CandidateProfile) -> list[RedFlag]:
    """Detect location claims that don't match experience."""
    flags = []
    # Basic check: if candidate lists a location but companies are all in very different regions
    # This is a lightweight heuristic — not a full geo analysis
    if not candidate.location or not candidate.experience:
        return flags

    locations = [e.location.lower() for e in candidate.experience if e.location]
    if not locations:
        return flags

    # If candidate claims location X but no experience mentions that region
    candidate_loc = candidate.location.lower()
    matches_any = any(
        candidate_loc in loc or loc in candidate_loc
        for loc in locations
    )

    if not matches_any and len(locations) >= 3:
        flags.append(RedFlag(
            category="geographic",
            severity=Severity.INFO,
            title="Location doesn't match experience locations",
            detail=(
                f"Claims current location: {candidate.location}, "
                f"but experience locations: {', '.join(set(locations[:5]))}"
            ),
            evidence=f"{candidate.location} vs {', '.join(set(locations[:5]))}",
            confidence=0.4,
            suggestion="May have recently relocated. Worth confirming.",
        ))

    return flags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> datetime | None:
    """Best-effort date parsing from various resume formats."""
    if not date_str or date_str.lower() in ("present", "current", "till date", "ongoing"):
        return datetime.now()

    for fmt in ("%b %Y", "%B %Y", "%m/%Y", "%Y-%m", "%Y-%m-%d", "%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    # Try extracting year+month with regex
    m = re.search(r"(\w+)\s+(\d{4})", date_str)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%B %Y")
        except ValueError:
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%b %Y")
            except ValueError:
                pass

    return None


def _overlap_months(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> int:
    """Calculate months of overlap between two date ranges."""
    overlap_start = max(s1, s2)
    overlap_end = min(e1, e2)
    if overlap_start >= overlap_end:
        return 0
    return (overlap_end.year - overlap_start.year) * 12 + (overlap_end.month - overlap_start.month)


def _build_summary(flags: list[RedFlag], risk_level: str, name: str) -> str:
    """Generate a human-readable summary."""
    if not flags:
        return f"{name}: Clean profile — no red flags detected."

    critical = [f for f in flags if f.severity == Severity.CRITICAL]
    warnings = [f for f in flags if f.severity == Severity.WARNING]

    parts = [f"{name}: {risk_level.upper()} risk"]
    if critical:
        parts.append(f"{len(critical)} critical issue(s): " +
                     ", ".join(f.title for f in critical))
    if warnings:
        parts.append(f"{len(warnings)} warning(s): " +
                     ", ".join(f.title for f in warnings))

    return ". ".join(parts) + "."
