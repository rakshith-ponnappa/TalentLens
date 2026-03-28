"""
verifier.py  –  Orchestrator that runs all verifications for a candidate:
  - All companies in experience
  - All certifications
  - LinkedIn profile (if provided)
  - Identity verification (email, education, web presence, timeline)
    → activated automatically when LinkedIn is absent
"""
from __future__ import annotations

from models import CandidateProfile, VerificationResults
from verifier_company import verify_companies
from verifier_certs import verify_certs
from verifier_linkedin import verify_linkedin, discover_linkedin
from verifier_identity import verify_identity
from config import Config, load_config


def run_verification(
    candidate: CandidateProfile,
    cfg: Config | None = None,
) -> VerificationResults:
    cfg = cfg or load_config()

    # --- Companies -------------------------------------------------------
    company_names = list({
        exp.company for exp in candidate.experience if exp.company.strip()
    })
    company_results = verify_companies(company_names, cfg.opencorporates_api_key)

    # --- Certifications --------------------------------------------------
    cert_results = verify_certs(candidate.certifications)

    # --- LinkedIn --------------------------------------------------------
    has_linkedin = bool(
        candidate.linkedin_url and "linkedin.com" in candidate.linkedin_url.lower()
    )
    if has_linkedin:
        li_result = verify_linkedin(candidate.linkedin_url, candidate.name)
    else:
        # No URL provided – try to discover the profile by name + company
        most_recent_company = ""
        most_recent_title = ""
        for exp in candidate.experience:
            if exp.company.strip() and exp.company != "Unknown":
                most_recent_company = exp.company
                most_recent_title = exp.title
                break
        li_result = discover_linkedin(
            name=candidate.name,
            company=most_recent_company,
            title=most_recent_title,
            location=candidate.location,
            email=candidate.email,
            phone=candidate.phone,
        )

    # --- Identity (always run; critical when no LinkedIn) ----------------
    id_result = verify_identity(candidate)

    # --- Trust score -----------------------------------------------------
    trust = _compute_trust(company_results, cert_results, li_result, id_result)

    return VerificationResults(
        companies=company_results,
        certifications=cert_results,
        linkedin=li_result,
        identity=id_result,
        overall_trust_score=trust,
    )


def _compute_trust(companies, certs, linkedin, identity) -> float:
    scores = []
    weights = []

    # Company legitimacy (average)
    if companies:
        avg = sum(c.legitimacy_score for c in companies) / len(companies)
        scores.append(avg)
        weights.append(0.30)

    # LinkedIn (if present)
    if linkedin and linkedin.url_resolves:
        scores.append(linkedin.authenticity_score)
        weights.append(0.25)

    # Registry presence for any claimed certs
    if certs:
        found = sum(1 for c in certs if c.found_in_registry) / len(certs)
        scores.append(found)
        weights.append(0.15)

    # Identity verification (email + education + web + timeline)
    if identity:
        scores.append(identity.overall_identity_score)
        # Give identity MORE weight when LinkedIn is missing
        weights.append(0.40 if not (linkedin and linkedin.url_resolves) else 0.20)

    if not scores:
        return 0.3  # No data at all

    # Weighted average
    total_weight = sum(weights)
    weighted = sum(s * w for s, w in zip(scores, weights)) / total_weight
    return round(max(0.0, min(1.0, weighted)), 2)
