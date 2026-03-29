"""
verifier.py  –  Orchestrator that runs all verifications for a candidate:
  - All companies via 9-layer online verification (Known DB → OpenCorporates →
    LinkedIn → Wikipedia/Wikidata → GitHub org → Domain/TLS → Job boards →
    DuckDuckGo → Crunchbase)
  - All certifications via 5-layer verification (Registry → Credly → Issuer
    pattern → Issuer website → Web search)
  - LinkedIn profile discovery + validation
  - Identity verification: email, education (Wikipedia-augmented), web presence
    (30+ platforms), and experience timeline analysis
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

    # Company legitimacy (average across all layers)
    if companies:
        avg = sum(c.legitimacy_score for c in companies) / len(companies)
        # Bonus: companies verified by multiple sources are more credible
        multi_source = sum(1 for c in companies if c.source and "," in c.source) / max(len(companies), 1)
        avg = min(1.0, avg + multi_source * 0.05)
        scores.append(avg)
        weights.append(0.30)

    # LinkedIn (if present)
    if linkedin and linkedin.url_resolves:
        scores.append(linkedin.authenticity_score)
        weights.append(0.25)

    # Certifications (registry + online verification)
    if certs:
        # Count both registry matches and online-verified certs
        verified = sum(
            1 for c in certs
            if c.found_in_registry or (c.issuer and c.issuer != "Unknown")
        ) / len(certs)
        scores.append(verified)
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
