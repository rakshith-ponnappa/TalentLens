"""
resume_parser.py  –  Parse a resume (PDF / DOCX / TXT) into CandidateProfile.

Two-stage:
  1. Raw text extraction
  2. LLM-based structured data extraction
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from config import Config, load_config
from llm_client import call_llm_json, NoLLMKeyError
from models import CandidateProfile, ExperienceEntry, EducationEntry
import heuristics


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def parse_resume(source: str | Path, cfg: Config | None = None) -> CandidateProfile:
    """
    source: file path (PDF/DOCX/TXT) OR raw text string.
    Returns a populated CandidateProfile.
    Falls back to heuristic (pattern-based) parsing if no LLM key is set.
    """
    cfg = cfg or load_config()
    p = Path(source) if isinstance(source, str) and Path(source).exists() else None
    source_file = str(p) if p else "pasted_text"
    text = _extract_text(source)
    try:
        return _parse_with_llm(text, source_file, cfg)
    except NoLLMKeyError:
        print(f"[heuristic mode] Parsing {Path(source_file).name} with pattern matching.", file=sys.stderr)
        return _parse_heuristic(text, source_file)


def parse_resumes(paths: list[str | Path], cfg: Config | None = None) -> list[CandidateProfile]:
    cfg = cfg or load_config()
    candidates = []
    for path in paths:
        try:
            candidates.append(parse_resume(path, cfg))
        except Exception as exc:
            print(f"[WARN] Failed to parse {path}: {exc}")
    return candidates


# --------------------------------------------------------------------------
# Text extraction (same helpers as jd_analyzer)
# --------------------------------------------------------------------------

def _extract_text(source: str | Path) -> str:
    p = Path(source) if isinstance(source, str) else source
    if p.exists():
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            return _read_pdf(p)
        if suffix in (".docx", ".doc"):
            return _read_docx(p)
        return p.read_text(encoding="utf-8", errors="ignore")
    return str(source)


def _read_pdf(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except ImportError:
        raise ImportError("Run: pip install pdfplumber")


def _read_docx(path: Path) -> str:
    try:
        from docx import Document
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except ImportError:
        raise ImportError("Run: pip install python-docx")


# --------------------------------------------------------------------------
# LLM extraction
# --------------------------------------------------------------------------

_SYSTEM = """You are an expert resume parser. Extract structured information from the 
resume text and return ONLY a JSON object with this exact schema:
{
  "name": "Full Name",
  "email": "email@example.com",
  "phone": "+1-555-...",
  "linkedin_url": "https://linkedin.com/in/...",
  "github_url": "https://github.com/...",
  "location": "City, State, Country",
  "skills": ["skill1", "skill2", ...],
  "certifications": ["AWS Certified Solutions Architect", ...],
  "experience": [
    {
      "company": "Company Name",
      "title": "Job Title",
      "start_date": "MM/YYYY or YYYY",
      "end_date": "MM/YYYY or Present",
      "duration_months": 24,
      "location": "City, State",
      "description": "Key responsibilities and achievements ..."
    }
  ],
  "education": [
    {
      "institution": "University Name",
      "degree": "Bachelor of Science",
      "field": "Computer Science",
      "graduation_year": 2019
    }
  ],
  "total_experience_years": 5.0
}
Rules:
- List ALL skills explicitly mentioned or implied by job titles/projects
- skills should be lowercase
- Include ALL jobs in experience, most recent first
- duration_months: calculate from start_date to end_date; 0 if unknown
- total_experience_years: sum of all professional experience (exclude overlaps)
- graduation_year: null if not stated
- Use empty string "" for missing text fields, empty list [] for missing arrays
"""


def _parse_with_llm(text: str, source_file: str, cfg: Config) -> CandidateProfile:
    prompt = f"Resume:\n\n{text[:8000]}"
    data = call_llm_json(prompt, _SYSTEM, cfg)

    experience = [
        ExperienceEntry(
            company=e.get("company", ""),
            title=e.get("title", ""),
            start_date=e.get("start_date", ""),
            end_date=e.get("end_date", ""),
            duration_months=int(e.get("duration_months", 0)),
            location=e.get("location", ""),
            description=e.get("description", ""),
        )
        for e in data.get("experience", [])
    ]

    education = [
        EducationEntry(
            institution=ed.get("institution", ""),
            degree=ed.get("degree", ""),
            field=ed.get("field", ""),
            graduation_year=ed.get("graduation_year"),
        )
        for ed in data.get("education", [])
    ]

    return CandidateProfile(
        name=data.get("name", "Unknown"),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        linkedin_url=data.get("linkedin_url", ""),
        github_url=data.get("github_url", ""),
        location=data.get("location", ""),
        skills=[s.lower().strip() for s in data.get("skills", [])],
        certifications=[c.strip() for c in data.get("certifications", [])],
        experience=experience,
        education=education,
        total_experience_years=float(data.get("total_experience_years", 0)),
        raw_text=text,
        source_file=source_file,
    )


# --------------------------------------------------------------------------
# Heuristic fallback (no LLM)
# --------------------------------------------------------------------------

def _parse_heuristic(text: str, source_file: str) -> CandidateProfile:
    """Pattern-based resume extraction – no API key required."""
    lines = [ln.strip() for ln in text.split('\n') if ln.strip()]

    email = heuristics.extract_email(text)
    phone = heuristics.extract_phone(text)
    linkedin = heuristics.extract_linkedin_url(text)
    github = heuristics.extract_github_url(text)
    location = heuristics.extract_location(text)
    name = heuristics.extract_name(lines, email)

    skills = sorted(heuristics.extract_skills(text))
    certs = heuristics.extract_certs(text)
    experience = heuristics.extract_experience_blocks(text)
    education = heuristics.extract_education_blocks(text)
    total_years = heuristics.calc_total_years(experience, text)

    return CandidateProfile(
        name=name,
        email=email,
        phone=phone,
        linkedin_url=linkedin,
        github_url=github,
        location=location,
        skills=skills,
        certifications=certs,
        experience=experience,
        education=education,
        total_experience_years=total_years,
        raw_text=text,
        source_file=source_file,
    )
