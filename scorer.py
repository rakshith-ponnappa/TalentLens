"""
scorer.py  –  Score and rank candidates against a JD.

Scoring components (configurable weights, default sum = 100):
  1. Required skills match   – 35 pts
  2. Preferred skills match  – 15 pts
  3. Experience years        – 25 pts
  4. Education level         – 10 pts
  5. Certifications          – 10 pts
  6. Semantic similarity     –  5 pts  (sentence-transformers, graceful fallback)
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional

from config import Config, load_config
from models import (
    CandidateProfile,
    CandidateScore,
    JDCriteria,
    ScoreBreakdown,
    VerificationResults,
)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def score_candidate(
    candidate: CandidateProfile,
    jd: JDCriteria,
    verification: Optional[VerificationResults] = None,
    cfg: Config | None = None,
) -> CandidateScore:
    cfg = cfg or load_config()
    w = cfg.weights

    # --- Required skills -------------------------------------------------
    matched_req, missing_req = _match_skills(candidate.skills, jd.required_skills, candidate.raw_text)
    req_score = (len(matched_req) / max(len(jd.required_skills), 1)) * w.required_skills

    # --- Preferred skills ------------------------------------------------
    matched_pref, _ = _match_skills(candidate.skills, jd.preferred_skills, candidate.raw_text)
    pref_score = (len(matched_pref) / max(len(jd.preferred_skills), 1)) * w.preferred_skills if jd.preferred_skills else w.preferred_skills

    # --- Experience years ------------------------------------------------
    exp_score = _score_experience(candidate.total_experience_years, jd, w.experience)

    # --- Education -------------------------------------------------------
    edu_score = _score_education(candidate.education, jd.education_level, w.education)

    # --- Certifications --------------------------------------------------
    cert_score = _score_certifications(
        candidate.certifications,
        jd.certifications_required,
        jd.certifications_preferred,
        w.certifications,
    )

    # --- Semantic similarity ---------------------------------------------
    sem_score = _semantic_score(candidate.raw_text, jd.raw_text, w.semantic)

    total = req_score + pref_score + exp_score + edu_score + cert_score + sem_score
    total = min(total, 100.0)

    return CandidateScore(
        candidate=candidate,
        overall_score=round(total, 1),
        similarity_pct=round(total, 1),
        grade=_grade(total),
        breakdown=ScoreBreakdown(
            required_skills=round(req_score, 1),
            preferred_skills=round(pref_score, 1),
            experience=round(exp_score, 1),
            education=round(edu_score, 1),
            certifications=round(cert_score, 1),
            semantic_similarity=round(sem_score, 1),
        ),
        matched_required_skills=matched_req,
        missing_required_skills=missing_req,
        matched_preferred_skills=matched_pref,
        rank=0,  # set after sorting
        verification=verification or VerificationResults(),
    )


def rank_candidates(scores: list[CandidateScore]) -> list[CandidateScore]:
    """Sort descending by score and assign rank numbers."""
    ranked = sorted(scores, key=lambda s: s.overall_score, reverse=True)
    for i, s in enumerate(ranked):
        s.rank = i + 1
    return ranked


# --------------------------------------------------------------------------
# Skill matching
# --------------------------------------------------------------------------

def _normalise(skill: str) -> str:
    return re.sub(r"[^a-z0-9+#.]", " ", skill.lower()).strip()


def _skill_match(candidate_skills: list[str], target: str, resume_text: str) -> bool:
    """True if target skill appears in candidate skills list OR resume text (fuzzy)."""
    t_norm = _normalise(target)
    text_lower = resume_text.lower()

    # Exact / contained match against skill list
    for s in candidate_skills:
        s_norm = _normalise(s)
        if t_norm in s_norm or s_norm in t_norm:
            return True
        # Fuzzy fallback for similar strings (e.g. "kubernetes" vs "k8s")
        if SequenceMatcher(None, t_norm, s_norm).ratio() > 0.82:
            return True

    # Aliases for common abbreviations
    aliases = {
        "kubernetes": ["k8s"],
        "javascript": ["js", "node.js", "nodejs"],
        "typescript": ["ts"],
        "python": ["py"],
        "amazon web services": ["aws"],
        "microsoft azure": ["azure"],
        "google cloud platform": ["gcp"],
        "continuous integration": ["ci/cd", "cicd"],
        "infrastructure as code": ["iac"],
    }
    for canonical, alias_list in aliases.items():
        if t_norm == canonical or t_norm in alias_list:
            check_terms = [canonical] + alias_list
            if any(term in text_lower for term in check_terms):
                return True

    # Plain text match in resume (for skills not explicitly listed)
    if t_norm in text_lower:
        return True

    return False


def _match_skills(
    candidate_skills: list[str],
    target_skills: list[str],
    resume_text: str,
) -> tuple[list[str], list[str]]:
    matched, missing = [], []
    for skill in target_skills:
        if _skill_match(candidate_skills, skill, resume_text):
            matched.append(skill)
        else:
            missing.append(skill)
    return matched, missing


# --------------------------------------------------------------------------
# Experience scoring
# --------------------------------------------------------------------------

def _score_experience(actual_years: float, jd: JDCriteria, weight: int) -> float:
    min_req = jd.min_experience_years
    max_req = jd.max_experience_years

    if min_req == 0:
        # No experience requirement – give full score
        return float(weight)

    if actual_years >= min_req:
        if max_req > 0 and actual_years > max_req * 1.5:
            # Over-qualified penalty (subtle)
            return weight * 0.85
        return float(weight)

    # Partial credit – proportional to how close they are
    ratio = actual_years / min_req
    return weight * ratio


# --------------------------------------------------------------------------
# Education scoring
# --------------------------------------------------------------------------

_EDU_RANK = {"any": 0, "bachelor": 1, "master": 2, "phd": 3}
_DEGREE_KEYWORDS = {
    "phd": 3, "doctorate": 3, "doctor of philosophy": 3,
    "master": 2, "msc": 2, "mba": 2, "m.s": 2, "m.eng": 2,
    "bachelor": 1, "bsc": 1, "b.s": 1, "b.eng": 1, "b.tech": 1,
    "associate": 0, "diploma": 0,
}


def _candidate_edu_rank(education: list) -> int:
    best = 0
    for e in education:
        deg_lower = e.degree.lower()
        for kw, rank in _DEGREE_KEYWORDS.items():
            if kw in deg_lower:
                best = max(best, rank)
    return best


def _score_education(education: list, required_level: str, weight: int) -> float:
    req_rank = _EDU_RANK.get(required_level.lower(), 0)
    if req_rank == 0:
        return float(weight)  # "Any" → full score

    candidate_rank = _candidate_edu_rank(education)
    if candidate_rank >= req_rank:
        return float(weight)
    # One level below: 60 %; two levels: 30 %
    gap = req_rank - candidate_rank
    return weight * max(0.0, 1.0 - gap * 0.35)


# --------------------------------------------------------------------------
# Certification scoring
# --------------------------------------------------------------------------

def _cert_fuzzy_match(candidate_certs: list[str], target: str) -> bool:
    t = target.lower()
    for c in candidate_certs:
        c_l = c.lower()
        if t in c_l or c_l in t:
            return True
        if SequenceMatcher(None, t, c_l).ratio() > 0.80:
            return True
    return False


def _score_certifications(
    candidate_certs: list[str],
    required: list[str],
    preferred: list[str],
    weight: int,
) -> float:
    if not required and not preferred:
        return float(weight)

    total_items = len(required) * 2 + len(preferred)  # required worth double
    earned = 0
    for c in required:
        if _cert_fuzzy_match(candidate_certs, c):
            earned += 2
    for c in preferred:
        if _cert_fuzzy_match(candidate_certs, c):
            earned += 1

    return (earned / max(total_items, 1)) * weight


# --------------------------------------------------------------------------
# Semantic similarity  (graceful fallback if transformers not installed)
# --------------------------------------------------------------------------

_embedder = None
_EMBED_LOADED = False


def _load_embedder():
    global _embedder, _EMBED_LOADED
    if _EMBED_LOADED:
        return
    _EMBED_LOADED = True
    try:
        from sentence_transformers import SentenceTransformer
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:  # broad catch: covers ImportError + scipy/sklearn compat issues
        _embedder = None


def _semantic_score(resume_text: str, jd_text: str, weight: int) -> float:
    """Combined semantic score: TF-IDF cosine (40%) + SBERT embedding (40%) + Jaccard (20%)."""
    scores: list[tuple[float, float]] = []  # (sim, weight_fraction)

    # --- TF-IDF cosine similarity ---
    tfidf_sim = _tfidf_similarity(resume_text, jd_text)
    scores.append((tfidf_sim, 0.40))

    # --- SBERT embedding similarity ---
    _load_embedder()
    if _embedder is not None:
        try:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity
            r_emb = _embedder.encode([resume_text[:2000]], convert_to_numpy=True)
            j_emb = _embedder.encode([jd_text[:2000]], convert_to_numpy=True)
            sbert_sim = float(cosine_similarity(r_emb, j_emb)[0][0])
            scores.append((sbert_sim, 0.40))
        except Exception:
            scores.append((tfidf_sim, 0.40))  # fallback to TF-IDF
    else:
        scores.append((tfidf_sim, 0.40))  # fallback

    # --- Jaccard word overlap ---
    r_words = set(re.findall(r"\b\w{4,}\b", resume_text.lower()))
    j_words = set(re.findall(r"\b\w{4,}\b", jd_text.lower()))
    jaccard = len(r_words & j_words) / max(len(r_words | j_words), 1)
    scores.append((jaccard, 0.20))

    combined = sum(sim * w for sim, w in scores)
    return combined * weight


def _tfidf_similarity(text_a: str, text_b: str) -> float:
    """Compute TF-IDF cosine similarity between two texts (no sklearn needed)."""
    import math
    from collections import Counter

    def _tokenise(text: str) -> list[str]:
        return re.findall(r"\b[a-z][a-z0-9+#.]{2,}\b", text.lower())

    tokens_a = _tokenise(text_a)
    tokens_b = _tokenise(text_b)

    if not tokens_a or not tokens_b:
        return 0.0

    tf_a = Counter(tokens_a)
    tf_b = Counter(tokens_b)

    # IDF over two-document "corpus"
    all_terms = set(tf_a.keys()) | set(tf_b.keys())
    idf = {}
    for term in all_terms:
        doc_freq = (1 if term in tf_a else 0) + (1 if term in tf_b else 0)
        idf[term] = math.log(2.0 / doc_freq) + 1  # smoothed IDF

    # TF-IDF vectors
    def _tfidf_vec(tf: Counter) -> dict[str, float]:
        total = sum(tf.values())
        return {t: (tf[t] / total) * idf.get(t, 1.0) for t in tf}

    vec_a = _tfidf_vec(tf_a)
    vec_b = _tfidf_vec(tf_b)

    # Cosine similarity
    common = set(vec_a.keys()) & set(vec_b.keys())
    if not common:
        return 0.0

    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


# --------------------------------------------------------------------------
# Skill gap analysis
# --------------------------------------------------------------------------

def compute_skill_gap(
    candidate_skills: list[str],
    resume_text: str,
    jd: "JDCriteria",
) -> dict:
    """Detailed skill gap analysis for a candidate against a JD."""
    matched_req, missing_req = _match_skills(candidate_skills, jd.required_skills, resume_text)
    matched_pref, missing_pref = _match_skills(candidate_skills, jd.preferred_skills, resume_text)

    # Categorise gaps by severity
    critical_gaps = missing_req[:5]      # required skills not found
    nice_to_have = missing_pref[:5]      # preferred skills not found

    # Extra skills not in JD (candidate's bonus)
    jd_all_lower = {s.lower() for s in jd.required_skills + jd.preferred_skills}
    extra_skills = [s for s in candidate_skills if s.lower() not in jd_all_lower]

    req_ratio = len(matched_req) / max(len(jd.required_skills), 1)
    pref_ratio = len(matched_pref) / max(len(jd.preferred_skills), 1)

    return {
        "required_match_pct": round(req_ratio * 100, 1),
        "preferred_match_pct": round(pref_ratio * 100, 1),
        "critical_gaps": critical_gaps,
        "nice_to_have_gaps": nice_to_have,
        "extra_skills": extra_skills[:10],
        "total_matched": len(matched_req) + len(matched_pref),
        "total_required": len(jd.required_skills) + len(jd.preferred_skills),
        "gap_severity": "Critical" if req_ratio < 0.5 else "Moderate" if req_ratio < 0.8 else "Low",
    }


# --------------------------------------------------------------------------
# Grade helper
# --------------------------------------------------------------------------

def _grade(score: float) -> str:
    if score >= 90: return "A+"
    if score >= 80: return "A"
    if score >= 70: return "B+"
    if score >= 60: return "B"
    if score >= 50: return "C"
    if score >= 40: return "D"
    return "F"
