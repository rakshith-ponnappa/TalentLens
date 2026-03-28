"""
jd_analyzer.py  –  Parse a Job Description into a structured JDCriteria object.

Accepts plain text, PDF, or DOCX.
Uses the LLM to extract criteria; falls back to keyword heuristics if LLM unavailable.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from config import Config, load_config
from llm_client import call_llm_json, NoLLMKeyError
from models import JDCriteria
import heuristics


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def analyze_jd(source: str | Path, cfg: Config | None = None) -> JDCriteria:
    """
    source: file path (PDF/DOCX/TXT) OR raw text string.
    Returns a populated JDCriteria.
    Falls back to heuristic (pattern-based) parsing if no LLM key is set.
    """
    cfg = cfg or load_config()
    text = _extract_text(source)
    try:
        return _parse_with_llm(text, cfg)
    except NoLLMKeyError:
        print("[heuristic mode] No LLM key – parsing JD with pattern matching.", file=sys.stderr)
        return _parse_heuristic(text)


# --------------------------------------------------------------------------
# Text extraction
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
    # Treat as raw text
    return str(source)


def _read_pdf(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
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

_SYSTEM = """You are an expert HR analyst. Extract structured hiring criteria from the 
given job description. Return ONLY a JSON object with these exact keys:
{
  "title": "...",
  "required_skills": ["skill1", "skill2", ...],
  "preferred_skills": ["skill1", ...],
  "min_experience_years": 3,
  "max_experience_years": 0,
  "education_level": "Bachelor",
  "certifications_required": [],
  "certifications_preferred": [],
  "industry": "...",
  "role_level": "Senior",
  "keywords": ["term1", "term2", ...]
}
Rules:
- required_skills: explicitly required or "must have"
- preferred_skills: "nice to have", "preferred", "plus"
- max_experience_years: 0 if no upper bound stated
- education_level: one of Any / Bachelor / Master / PhD
- role_level: Junior / Mid / Senior / Lead / Principal / Executive
- keywords: important domain terms that should appear on a strong resume
"""


def _parse_with_llm(text: str, cfg: Config) -> JDCriteria:
    prompt = f"Job Description:\n\n{text[:8000]}"
    data = call_llm_json(prompt, _SYSTEM, cfg)

    return JDCriteria(
        title=data.get("title", "Unknown Role"),
        required_skills=[s.lower().strip() for s in data.get("required_skills", [])],
        preferred_skills=[s.lower().strip() for s in data.get("preferred_skills", [])],
        min_experience_years=float(data.get("min_experience_years", 0)),
        max_experience_years=float(data.get("max_experience_years", 0)),
        education_level=data.get("education_level", "Any"),
        certifications_required=[c.strip() for c in data.get("certifications_required", [])],
        certifications_preferred=[c.strip() for c in data.get("certifications_preferred", [])],
        industry=data.get("industry", "General"),
        role_level=data.get("role_level", "Mid"),
        keywords=[k.lower().strip() for k in data.get("keywords", [])],
        raw_text=text,
    )


# --------------------------------------------------------------------------
# Heuristic fallback (no LLM)
# --------------------------------------------------------------------------

def _parse_heuristic(text: str) -> JDCriteria:
    """Pattern-based JD extraction – no API key required."""
    req_section, pref_section = heuristics.split_jd_sections(text)

    all_skills = heuristics.extract_skills(text)
    req_skills = heuristics.extract_skills(req_section) if req_section != text else all_skills
    pref_skills = heuristics.extract_skills(pref_section) - req_skills if pref_section else set()

    certs_all = heuristics.extract_certs(text)
    certs_req = heuristics.extract_certs(req_section) if req_section != text else certs_all
    certs_pref = [c for c in heuristics.extract_certs(pref_section) if c not in certs_req]

    title = heuristics.extract_jd_title(text)
    min_exp, max_exp = heuristics.extract_experience_range(text)
    edu_level = heuristics.extract_education_level(text)
    role_level = heuristics.extract_role_level(text, title)
    industry = heuristics.infer_industry(text)

    keywords = sorted(all_skills)[:20]

    return JDCriteria(
        title=title,
        required_skills=sorted(req_skills),
        preferred_skills=sorted(pref_skills),
        min_experience_years=min_exp,
        max_experience_years=max_exp,
        education_level=edu_level,
        certifications_required=certs_req,
        certifications_preferred=certs_pref,
        industry=industry,
        role_level=role_level,
        keywords=keywords,
        raw_text=text,
    )
