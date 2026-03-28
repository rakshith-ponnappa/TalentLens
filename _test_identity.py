"""Test identity verification with and without LinkedIn."""
import os
os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

from models import CandidateProfile, ExperienceEntry, EducationEntry
from verifier_identity import verify_identity, verify_email, verify_timeline

# --- Candidate WITHOUT LinkedIn ---
candidate_no_li = CandidateProfile(
    name="John Smith",
    email="john.smith@acmecloudsolutions.com",
    phone="+1-555-123-4567",
    linkedin_url="",  # NO LinkedIn
    github_url="https://github.com/jsmith",
    location="Austin, TX",
    skills=["aws", "terraform", "python"],
    experience=[
        ExperienceEntry(
            company="Acme Cloud Solutions",
            title="Senior Cloud Engineer",
            start_date="Jan 2021",
            end_date="Present",
            duration_months=51,
            location="Austin, TX",
            description="Led AWS migration",
        ),
        ExperienceEntry(
            company="TechCorp Inc",
            title="Cloud Engineer",
            start_date="Mar 2018",
            end_date="Dec 2020",
            duration_months=33,
            location="Austin, TX",
            description="Managed AWS infra",
        ),
    ],
    education=[
        EducationEntry(
            institution="University of Texas",
            degree="Bachelor of Science",
            field="Computer Science",
            graduation_year=2017,
        ),
    ],
    certifications=["AWS Certified Solutions Architect"],
    total_experience_years=7.0,
    raw_text="...",
    source_file="test.pdf",
)

print("=" * 60)
print("TEST: Candidate WITHOUT LinkedIn")
print("=" * 60)

result = verify_identity(candidate_no_li)
print(f"Method:       {result.method}")
print(f"Identity Score: {result.overall_identity_score:.0%}")
print()

if result.email:
    e = result.email
    print(f"Email: {e.address}")
    print(f"  Format valid: {e.format_valid}")
    print(f"  Domain: {e.domain} ({e.domain_type})")
    print(f"  MX exists: {e.mx_record_exists}")
    print(f"  Matches employer: {e.domain_matches_employer}")

if result.education:
    for edu in result.education:
        print(f"Education: {edu.institution} -> found={edu.found_online} ({edu.source})")

if result.timeline:
    tl = result.timeline
    print(f"Timeline: plausible={tl.timeline_plausible}")
    print(f"  Claimed: {tl.total_claimed_years} yrs | Calculated: {tl.calculated_years} yrs")
    for g in tl.gap_details:
        print(f"  Gap: {g}")
    for o in tl.overlap_details:
        print(f"  Overlap: {o}")

if result.web_presence:
    wp = result.web_presence
    print(f"Web presence: score={wp.presence_score:.0%}, profiles={wp.results_found}")
    for p in wp.professional_profiles:
        print(f"  -> {p}")
    for f in wp.red_flags:
        print(f"  FLAG: {f}")

print()

# --- Test with disposable email ---
print("=" * 60)
print("TEST: Disposable email")
print("=" * 60)
ev = verify_email("john@mailinator.com", [])
if ev:
    print(f"Domain type: {ev.domain_type}")
    print(f"Notes: {ev.notes}")

# --- Test with gap in timeline ---
print()
print("=" * 60)
print("TEST: Timeline with gap")
print("=" * 60)
exp_with_gap = [
    ExperienceEntry("Co A", "Engineer", "Jan 2016", "Dec 2017", 24, "", ""),
    ExperienceEntry("Co B", "Sr Engineer", "Jan 2020", "Present", 63, "", ""),
]
tl = verify_timeline(exp_with_gap, 8.0)
if tl:
    print(f"Has gaps: {tl.has_gaps}")
    for g in tl.gap_details:
        print(f"  {g}")
    print(f"Plausible: {tl.timeline_plausible}")
    print(f"  Claimed: {tl.total_claimed_years} | Calc: {tl.calculated_years}")
