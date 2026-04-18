"""
Shared pytest fixtures for resume-screener tests.

Provides realistic JDCriteria, CandidateProfile, CandidateScore,
and VerificationResults objects for use across all test modules.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import (
    CandidateProfile,
    CandidateScore,
    EducationEntry,
    ExperienceEntry,
    JDCriteria,
    ScoreBreakdown,
    VerificationResults,
)

# ---------------------------------------------------------------------------
# JD fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_jd() -> JDCriteria:
    return JDCriteria(
        title="Senior Cloud Engineer",
        required_skills=["terraform", "kubernetes", "aws", "python", "ci/cd"],
        preferred_skills=["azure", "helm", "prometheus", "golang"],
        min_experience_years=5,
        max_experience_years=12,
        education_level="Bachelor",
        certifications_required=["AWS Solutions Architect"],
        certifications_preferred=["CKA", "HashiCorp Terraform Associate"],
        industry="Technology",
        role_level="Senior",
        keywords=["infrastructure as code", "devops", "cloud native"],
        raw_text=(
            "Senior Cloud Engineer needed. 5-12 years experience. "
            "Must know Terraform, Kubernetes, AWS, Python, CI/CD. "
            "AWS Solutions Architect required. Bachelor's degree."
        ),
    )


# ---------------------------------------------------------------------------
# Candidate fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_candidate() -> CandidateProfile:
    return CandidateProfile(
        name="Alice Johnson",
        email="alice.johnson@example.com",
        phone="+1-555-123-4567",
        linkedin_url="https://linkedin.com/in/alicejohnson",
        github_url="https://github.com/alicejohnson",
        location="San Francisco, CA",
        skills=["terraform", "kubernetes", "aws", "python", "docker", "ci/cd", "azure"],
        experience=[
            ExperienceEntry(
                company="CloudCorp Inc.",
                title="Senior DevOps Engineer",
                start_date="2020-01",
                end_date="Present",
                duration_months=63,
                location="San Francisco, CA",
                description="Led cloud infrastructure with Terraform and Kubernetes on AWS.",
            ),
            ExperienceEntry(
                company="DataSoft LLC",
                title="Cloud Engineer",
                start_date="2017-06",
                end_date="2019-12",
                duration_months=30,
                location="Austin, TX",
                description="Built CI/CD pipelines and managed AWS workloads.",
            ),
            ExperienceEntry(
                company="StartupXYZ",
                title="Junior Developer",
                start_date="2015-01",
                end_date="2017-05",
                duration_months=28,
                location="Boston, MA",
                description="Python backend development and basic AWS usage.",
            ),
        ],
        education=[
            EducationEntry(
                institution="MIT",
                degree="BS",
                field="Computer Science",
                graduation_year=2014,
            ),
        ],
        certifications=["AWS Solutions Architect", "CKA"],
        total_experience_years=10.1,
        raw_text="Alice Johnson resume text...",
        source_file="alice_johnson_resume.pdf",
    )


@pytest.fixture
def weak_candidate() -> CandidateProfile:
    """Candidate with minimal experience and gaps — triggers red flags."""
    return CandidateProfile(
        name="Bob Weak",
        email="bob@yopmail.com",
        phone="",
        linkedin_url="",
        github_url="",
        location="Unknown",
        skills=["python"],
        experience=[
            ExperienceEntry(
                company="Freelance",
                title="CTO",
                start_date="2023-01",
                end_date="2023-06",
                duration_months=5,
                location="Remote",
                description="Freelance consulting.",
            ),
            ExperienceEntry(
                company="SomePlace",
                title="Intern",
                start_date="2021-01",
                end_date="2021-06",
                duration_months=5,
                location="NYC",
                description="Internship.",
            ),
        ],
        education=[
            EducationEntry(
                institution="Unknown University",
                degree="BS",
                field="IT",
                graduation_year=2035,
            ),
        ],
        certifications=[],
        total_experience_years=1.5,
        raw_text="Bob weak resume text...",
        source_file="bob_weak.pdf",
    )


# ---------------------------------------------------------------------------
# Score fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_score(sample_candidate, sample_jd) -> CandidateScore:
    return CandidateScore(
        candidate=sample_candidate,
        overall_score=82.5,
        similarity_pct=78.0,
        grade="A",
        breakdown=ScoreBreakdown(
            required_skills=30.0,
            preferred_skills=10.0,
            experience=22.0,
            education=8.0,
            certifications=9.0,
            semantic_similarity=3.5,
        ),
        matched_required_skills=["terraform", "kubernetes", "aws", "python", "ci/cd"],
        missing_required_skills=[],
        matched_preferred_skills=["azure"],
        rank=1,
        verification=VerificationResults(overall_trust_score=0.85),
    )


@pytest.fixture
def weak_score(weak_candidate, sample_jd) -> CandidateScore:
    return CandidateScore(
        candidate=weak_candidate,
        overall_score=28.0,
        similarity_pct=22.0,
        grade="D",
        breakdown=ScoreBreakdown(
            required_skills=5.0,
            preferred_skills=0.0,
            experience=8.0,
            education=5.0,
            certifications=0.0,
            semantic_similarity=1.0,
        ),
        matched_required_skills=["python"],
        missing_required_skills=["terraform", "kubernetes", "aws", "ci/cd"],
        matched_preferred_skills=[],
        rank=2,
        verification=VerificationResults(overall_trust_score=0.2),
    )


# ---------------------------------------------------------------------------
# Temp directory for output tests
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_output(tmp_path):
    """Return a temporary directory for export tests."""
    return tmp_path
