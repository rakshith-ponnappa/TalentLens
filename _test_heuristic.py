"""Quick smoke test for heuristic mode (no LLM key)."""
import os
import sys

os.environ["OPENAI_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

sys.path.insert(0, ".")

from config import load_config
from jd_analyzer import analyze_jd
from resume_parser import parse_resume
from scorer import score_candidate

JD = "\n".join([
    "AWS Migration Engineer - Senior",
    "4+ Years Experience Required",
    "",
    "Requirements:",
    "- 4+ years of hands-on AWS experience",
    "- AWS services: EC2, S3, RDS, VPC, IAM, CloudWatch",
    "- Cloud migration: lift-and-shift, re-platform, re-architecture",
    "- Terraform and CloudFormation",
    "- AWS DMS, AWS MGN, AWS Migration Hub",
    "- Linux administration",
    "- Python or Bash scripting",
    "- Agile/DevOps",
    "",
    "Preferred:",
    "- AWS Certified Solutions Architect Associate or Professional",
    "- AWS Control Tower and AWS Organizations",
    "- Kubernetes / EKS",
    "- GitHub Actions or Jenkins",
    "",
    "Education: Bachelors degree in Computer Science",
])

RESUME = "\n".join([
    "John Smith",
    "john.smith@example.com | +1-555-123-4567",
    "linkedin.com/in/johnsmith | github.com/jsmith",
    "Austin, TX",
    "",
    "EXPERIENCE",
    "",
    "Senior Cloud Engineer | Acme Cloud Solutions | Jan 2021 - Present",
    "Led AWS migration using lift-and-shift and re-platform strategies",
    "Used AWS MGN and AWS DMS for migrations",
    "Built Terraform modules for EC2, S3, RDS, VPC, IAM",
    "Implemented AWS Landing Zone using Control Tower and AWS Organizations",
    "Automated CI/CD pipelines with GitHub Actions",
    "",
    "Cloud Engineer | TechCorp Inc | Mar 2018 - Dec 2020",
    "Managed AWS infrastructure: EC2, S3, RDS, CloudWatch, Route 53",
    "Wrote Python and Bash automation scripts",
    "Deployed Kubernetes clusters on EKS",
    "Supported Linux servers and on-premises VMware",
    "",
    "EDUCATION",
    "Bachelor of Science in Computer Science",
    "University of Texas, Austin | 2017",
    "",
    "CERTIFICATIONS",
    "AWS Certified Solutions Architect - Associate (SAA-C03)",
    "AWS Certified Developer - Associate",
])

cfg = load_config()

jd = analyze_jd(JD, cfg)
print(f"Title:          {jd.title}")
print(f"Role:           {jd.role_level}  |  Min exp: {jd.min_experience_years} yrs")
print(f"Required skills ({len(jd.required_skills)}): {jd.required_skills[:8]}")
print(f"Preferred:      {jd.preferred_skills[:5]}")

candidate = parse_resume(RESUME, cfg)
print(f"\nName:     {candidate.name}")
print(f"Email:    {candidate.email}")
print(f"LinkedIn: {candidate.linkedin_url}")
print(f"Skills ({len(candidate.skills)}): {candidate.skills[:8]}")
print(f"Exp:      {candidate.total_experience_years} yrs")
print(f"Certs:    {candidate.certifications}")

score = score_candidate(candidate, jd, cfg=cfg)
print(f"\nSCORE:   {score.overall_score}/100   Grade: {score.grade}")
print(f"Matched: {score.matched_required_skills}")
print(f"Missing: {score.missing_required_skills}")
