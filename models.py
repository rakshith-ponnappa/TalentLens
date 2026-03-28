"""
Data models for the resume screening pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Job Description
# ---------------------------------------------------------------------------

@dataclass
class JDCriteria:
    title: str
    required_skills: list[str]
    preferred_skills: list[str]
    min_experience_years: float
    max_experience_years: float          # 0 = not specified
    education_level: str                 # "Any", "Bachelor", "Master", "PhD"
    certifications_required: list[str]
    certifications_preferred: list[str]
    industry: str
    role_level: str                      # Junior / Mid / Senior / Lead / Principal
    keywords: list[str]                  # extra important terms
    raw_text: str


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------

@dataclass
class ExperienceEntry:
    company: str
    title: str
    start_date: str
    end_date: str                        # "Present" if current
    duration_months: int
    location: str
    description: str


@dataclass
class EducationEntry:
    institution: str
    degree: str                          # BS, MS, PhD, Diploma …
    field: str
    graduation_year: Optional[int]


@dataclass
class CandidateProfile:
    name: str
    email: str
    phone: str
    linkedin_url: str
    github_url: str
    location: str
    skills: list[str]
    experience: list[ExperienceEntry]
    education: list[EducationEntry]
    certifications: list[str]
    total_experience_years: float
    raw_text: str
    source_file: str


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

@dataclass
class CompanyVerification:
    name: str
    found: bool
    source: str                          # "OpenCorporates", "LinkedIn", "Google"
    employee_count: str                  # "1-10", "11-50", "51-200" …
    company_type: str                    # Startup / SME / Enterprise / Fortune500
    founded_year: Optional[int]
    status: str                          # Active / Dissolved / Unknown
    legitimacy_score: float              # 0.0 – 1.0
    notes: str


@dataclass
class CertVerification:
    name: str
    issuer: str
    found_in_registry: bool
    verification_url: str
    manually_verifiable: bool
    notes: str


@dataclass
class LinkedInVerification:
    url: str
    url_resolves: bool
    profile_name: str
    headline: str
    connections_label: str               # "500+" etc.
    profile_completeness: str            # High / Medium / Low
    authenticity_score: float            # 0.0 – 1.0
    red_flags: list[str]
    notes: str


@dataclass
class EmailVerification:
    address: str
    format_valid: bool
    domain: str
    domain_type: str                     # Corporate / Personal / Disposable / Unknown
    domain_matches_employer: bool        # domain matches a claimed company?
    mx_record_exists: bool               # DNS MX lookup
    deliverable: str                     # Yes / No / Unknown
    notes: str


@dataclass
class EducationVerification:
    institution: str
    found_online: bool
    source: str                          # "Web search" / "Known registry"
    degree_programs_plausible: bool      # institution offers claimed degree type
    notes: str


@dataclass
class WebPresenceCheck:
    name: str
    search_query: str
    results_found: int
    name_company_cooccurrence: bool      # name + company appear together online
    professional_profiles: list[str]     # URLs of found profiles (GitHub, StackOverflow, etc.)
    red_flags: list[str]
    presence_score: float                # 0.0 – 1.0
    notes: str


@dataclass
class ExperienceTimeline:
    has_gaps: bool
    gap_details: list[str]              # "Gap: May 2019 – Jan 2020 (8 months)"
    has_overlaps: bool
    overlap_details: list[str]
    total_claimed_years: float
    calculated_years: float
    timeline_plausible: bool
    notes: str


@dataclass
class IdentityVerification:
    email: Optional[EmailVerification] = None
    education: list[EducationVerification] = field(default_factory=list)
    web_presence: Optional[WebPresenceCheck] = None
    timeline: Optional[ExperienceTimeline] = None
    overall_identity_score: float = 0.0  # 0.0 – 1.0
    method: str = ""                     # "LinkedIn" / "Alternative" / "Partial"


@dataclass
class VerificationResults:
    companies: list[CompanyVerification] = field(default_factory=list)
    certifications: list[CertVerification] = field(default_factory=list)
    linkedin: Optional[LinkedInVerification] = None
    identity: Optional[IdentityVerification] = None
    overall_trust_score: float = 0.0     # 0.0 – 1.0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

@dataclass
class ScoreBreakdown:
    required_skills: float               # 0 – weight
    preferred_skills: float
    experience: float
    education: float
    certifications: float
    semantic_similarity: float


@dataclass
class CandidateScore:
    candidate: CandidateProfile
    overall_score: float                 # 0 – 100
    similarity_pct: float                # percentage match label
    grade: str                           # A+ / A / B+ / B / C / D / F
    breakdown: ScoreBreakdown
    matched_required_skills: list[str]
    missing_required_skills: list[str]
    matched_preferred_skills: list[str]
    rank: int
    verification: VerificationResults
