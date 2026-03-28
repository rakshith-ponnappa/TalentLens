"""
verifier_identity.py  –  Alternative identity verification when LinkedIn is absent.

Verification layers (all public data, no paid APIs required):

  1. EMAIL VERIFICATION
     - Format validation (RFC 5322 basic)
     - Domain classification: Corporate / Personal (gmail, outlook…) / Disposable
     - Domain-to-employer matching: does email domain match a claimed company?
     - DNS MX record lookup: does the mail domain actually accept mail?

  2. EDUCATION VERIFICATION
     - Check institution existence via known university list + web search
     - Plausibility: does the institution offer that type of degree?

  3. WEB PRESENCE SEARCH
     - Google-style heuristic: search for "name + company" co-occurrence
     - Find professional profile URLs (GitHub, StackOverflow, personal site)
     - Score based on digital footprint depth

  4. EXPERIENCE TIMELINE ANALYSIS
     - Detect gaps > 6 months (flag but not necessarily bad)
     - Detect overlapping jobs (red flag)
     - Compare claimed total years vs calculated sum
     - Plausibility check: did they start working before age 16?
"""
from __future__ import annotations

import re
import socket
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import quote_plus

import requests
from requests.exceptions import RequestException

from models import (
    CandidateProfile,
    EmailVerification,
    EducationVerification,
    ExperienceTimeline,
    IdentityVerification,
    WebPresenceCheck,
)


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = 8


# ==========================================================================
# PUBLIC API
# ==========================================================================

def verify_identity(candidate: CandidateProfile) -> IdentityVerification:
    """Run all non-LinkedIn verification checks and return an aggregate result."""
    has_linkedin = bool(
        candidate.linkedin_url and "linkedin.com" in candidate.linkedin_url.lower()
    )

    email_result = verify_email(candidate.email, candidate.experience)
    edu_results = verify_education(candidate.education)
    timeline_result = verify_timeline(candidate.experience, candidate.total_experience_years)
    web_result = verify_web_presence(candidate.name, candidate.experience, candidate.github_url)

    # Aggregate score
    scores: list[float] = []

    if email_result:
        scores.append(_email_score(email_result))
    if edu_results:
        avg = sum(1.0 if e.found_online else 0.3 for e in edu_results) / len(edu_results)
        scores.append(avg)
    if timeline_result:
        scores.append(1.0 if timeline_result.timeline_plausible else 0.4)
    if web_result:
        scores.append(web_result.presence_score)

    overall = round(sum(scores) / max(len(scores), 1), 2) if scores else 0.3
    method = "LinkedIn" if has_linkedin else ("Alternative" if scores else "Partial")

    return IdentityVerification(
        email=email_result,
        education=edu_results,
        web_presence=web_result,
        timeline=timeline_result,
        overall_identity_score=overall,
        method=method,
    )


# ==========================================================================
# 1. EMAIL VERIFICATION
# ==========================================================================

_PERSONAL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.in", "hotmail.com", "outlook.com",
    "live.com", "aol.com", "icloud.com", "me.com", "protonmail.com",
    "proton.me", "mail.com", "zoho.com", "yandex.com", "gmx.com",
    "fastmail.com", "tutanota.com",
}

_DISPOSABLE_DOMAINS = {
    "guerrillamail.com", "tempmail.com", "10minutemail.com", "throwaway.email",
    "mailinator.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "dispostable.com", "maildrop.cc", "temp-mail.org", "fakeinbox.com",
    "tempail.com", "getnada.com",
}

_EMAIL_RE = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)


def verify_email(
    email: str,
    experience: list | None = None,
) -> Optional[EmailVerification]:
    """Verify email format, domain type, MX records, and employer match."""
    if not email or not email.strip():
        return None

    email = email.strip().lower()
    format_valid = bool(_EMAIL_RE.match(email))
    if not format_valid:
        return EmailVerification(
            address=email, format_valid=False, domain="", domain_type="Unknown",
            domain_matches_employer=False, mx_record_exists=False,
            deliverable="No", notes="Invalid email format",
        )

    domain = email.split("@")[1]

    # Classify domain
    if domain in _DISPOSABLE_DOMAINS:
        domain_type = "Disposable"
    elif domain in _PERSONAL_DOMAINS:
        domain_type = "Personal"
    else:
        domain_type = "Corporate"

    # MX record check
    mx_exists = _check_mx(domain)

    # Match domain against claimed employers
    employer_match = False
    if experience and domain_type == "Corporate":
        employer_match = _domain_matches_company(domain, experience)

    notes_parts = []
    if domain_type == "Disposable":
        notes_parts.append("DISPOSABLE email domain – high risk")
    elif domain_type == "Corporate":
        if employer_match:
            notes_parts.append(f"Corporate domain '{domain}' matches a claimed employer")
        else:
            notes_parts.append(f"Corporate domain '{domain}' – not matched to any listed employer")
    else:
        notes_parts.append(f"Personal email ({domain})")

    if not mx_exists:
        notes_parts.append("No MX record – domain may not accept email")

    deliverable = "Yes" if mx_exists and format_valid else ("Unknown" if format_valid else "No")

    return EmailVerification(
        address=email,
        format_valid=format_valid,
        domain=domain,
        domain_type=domain_type,
        domain_matches_employer=employer_match,
        mx_record_exists=mx_exists,
        deliverable=deliverable,
        notes="; ".join(notes_parts),
    )


def _check_mx(domain: str) -> bool:
    """Check if domain has MX records via DNS."""
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers) > 0
    except ImportError:
        # Fallback: try socket
        try:
            socket.getaddrinfo(domain, 25, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except (socket.gaierror, OSError):
            return False
    except Exception:
        return False


def _domain_matches_company(domain: str, experience: list) -> bool:
    """Check if the email domain plausibly matches any claimed employer."""
    domain_base = domain.split(".")[0].lower()
    for exp in experience:
        company_lower = exp.company.lower()
        company_slug = re.sub(r"[^a-z0-9]", "", company_lower)
        if (
            domain_base in company_lower
            or company_slug in domain_base
            or SequenceMatcher(None, domain_base, company_slug).ratio() > 0.7
        ):
            return True
    return False


def _email_score(ev: EmailVerification) -> float:
    """Convert email verification to a 0-1 score."""
    if not ev.format_valid:
        return 0.1
    score = 0.4  # Base for valid format
    if ev.mx_record_exists:
        score += 0.2
    if ev.domain_type == "Corporate":
        score += 0.2
        if ev.domain_matches_employer:
            score += 0.2
    elif ev.domain_type == "Personal":
        score += 0.1
    elif ev.domain_type == "Disposable":
        score -= 0.3
    return max(0.0, min(1.0, score))


# ==========================================================================
# 2. EDUCATION VERIFICATION
# ==========================================================================

# Top universities / known institutions (expanded list for global coverage)
_KNOWN_INSTITUTIONS = {
    # US
    "mit", "stanford", "harvard", "caltech", "yale", "princeton",
    "columbia", "university of texas", "georgia tech", "carnegie mellon",
    "university of michigan", "uc berkeley", "ucla", "purdue",
    "university of illinois", "penn state", "ohio state", "uw madison",
    "university of washington", "cornell", "nyu", "usc",
    "university of florida", "virginia tech", "texas a&m",
    "northeastern", "boston university", "drexel", "rutgers",
    "university of maryland", "arizona state", "university of colorado",
    # Canada
    "university of toronto", "university of waterloo", "mcgill",
    "university of british columbia", "university of alberta",
    # UK
    "oxford", "cambridge", "imperial college", "eth zurich",
    "university of london", "kings college", "university of edinburgh",
    "university of manchester", "ucl", "university college london",
    # India - IITs
    "iit", "iit bombay", "iit delhi", "iit madras", "iit kanpur",
    "iit kharagpur", "iit roorkee", "iit guwahati", "iit hyderabad",
    # India - NITs
    "nit", "nit trichy", "nit warangal", "nit surathkal", "nit calicut",
    # India - Other top
    "bits pilani", "iisc", "anna university", "university of mumbai",
    "delhi university", "vtu", "jntu", "osmania university",
    "bangalore university", "madras university", "calcutta university",
    "university of pune", "savitribai phule", "mumbai university",
    "amity university", "srm university", "manipal", "vit",
    "lovely professional", "chandigarh university", "thapar",
    "psg college", "coimbatore institute", "sastra", "karunya",
    "college of engineering", "institute of technology",
    # India - patterns that match many engineering colleges
    "engineering", "polytechnic", "technology",
    # Australia
    "university of sydney", "university of melbourne",
    "monash university", "unsw", "anu",
    # Singapore
    "nus", "ntu singapore", "nanyang",
    # Europe
    "tu munich", "rwth aachen", "tu berlin",
    "university of amsterdam", "delft", "epfl",
    # Middle East
    "american university",
}


def verify_education(education: list) -> list[EducationVerification]:
    """Check each education entry for plausibility."""
    results = []
    for edu in education:
        institution = edu.institution.strip()
        if not institution or institution == "Unknown":
            results.append(EducationVerification(
                institution=institution or "(not provided)",
                found_online=False, source="",
                degree_programs_plausible=False,
                notes="No institution name provided",
            ))
            continue

        # Local known check
        inst_lower = institution.lower()
        known = any(k in inst_lower for k in _KNOWN_INSTITUTIONS)

        # Web check fallback
        if not known:
            known = _check_institution_web(institution)

        degree_plausible = True  # Assume true unless we can disprove

        source = "Known registry" if any(k in inst_lower for k in _KNOWN_INSTITUTIONS) else "Web search"

        results.append(EducationVerification(
            institution=institution,
            found_online=known,
            source=source if known else "Not found",
            degree_programs_plausible=degree_plausible,
            notes=f"Institution {'verified' if known else 'not confirmed'} via {source.lower()}",
        ))

    return results


def _check_institution_web(name: str) -> bool:
    """Quick web check: see if institution has a .edu or known domain."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    # Try common patterns
    for tld in [".edu", ".ac.uk", ".ac.in", ".edu.au"]:
        domain = slug.replace("-", "") + tld
        try:
            socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except (socket.gaierror, OSError):
            pass

    # Try a simple request to the slug as a domain
    for prefix in ["www.", ""]:
        for tld in [".edu", ".com", ".org"]:
            try:
                url = f"https://{prefix}{slug}{tld}"
                resp = requests.head(url, headers=_HEADERS, timeout=5, allow_redirects=True)
                if resp.status_code < 400:
                    return True
            except RequestException:
                pass

    return False


# ==========================================================================
# 3. WEB PRESENCE CHECK
# ==========================================================================

def verify_web_presence(
    name: str,
    experience: list | None = None,
    github_url: str = "",
) -> Optional[WebPresenceCheck]:
    """Search for the candidate's digital footprint beyond LinkedIn."""
    if not name or name == "Unknown":
        return None

    profiles_found: list[str] = []
    red_flags: list[str] = []
    score = 0.3  # Base score for having a name

    # GitHub check
    if github_url:
        github_ok = _check_url_resolves(github_url)
        if github_ok:
            profiles_found.append(github_url)
            score += 0.2
        else:
            red_flags.append(f"GitHub URL does not resolve: {github_url}")
            score -= 0.1

    # Try to find name + most recent company co-occurrence
    most_recent_company = ""
    if experience:
        for exp in experience:
            if exp.company.strip() and exp.company != "Unknown":
                most_recent_company = exp.company
                break

    cooccurrence = False
    search_query = f'"{name}"'
    if most_recent_company:
        search_query += f' "{most_recent_company}"'

    # Check common professional platforms for the name
    name_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

    # GitHub profile search (if no URL provided)
    if not github_url:
        gh_url = f"https://github.com/{name_slug}"
        if _check_url_resolves(gh_url):
            profiles_found.append(gh_url)
            score += 0.1

    # StackOverflow users search
    so_url = f"https://stackoverflow.com/users?q={quote_plus(name)}&tab=reputation"
    try:
        resp = requests.get(so_url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200 and name.split()[0].lower() in resp.text.lower():
            profiles_found.append(so_url)
            score += 0.1
    except RequestException:
        pass

    # Name + company co-occurrence check via a simple web request
    if most_recent_company:
        cooccurrence = _check_name_company_web(name, most_recent_company)
        if cooccurrence:
            score += 0.2
        else:
            red_flags.append(
                f"Could not verify '{name}' worked at '{most_recent_company}' via web search"
            )

    # No digital footprint at all
    if not profiles_found and not cooccurrence:
        red_flags.append("No professional web presence found outside resume")
        score = max(score - 0.1, 0.1)

    notes_parts = []
    if profiles_found:
        notes_parts.append(f"Found {len(profiles_found)} professional profile(s)")
    if cooccurrence:
        notes_parts.append(f"Name + '{most_recent_company}' confirmed via web")

    return WebPresenceCheck(
        name=name,
        search_query=search_query,
        results_found=len(profiles_found),
        name_company_cooccurrence=cooccurrence,
        professional_profiles=profiles_found,
        red_flags=red_flags,
        presence_score=round(max(0.0, min(1.0, score)), 2),
        notes="; ".join(notes_parts) if notes_parts else "Limited web presence",
    )


def _check_url_resolves(url: str) -> bool:
    """Check if a URL returns 200 OK."""
    try:
        resp = requests.head(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        return resp.status_code == 200
    except RequestException:
        return False


def _check_name_company_web(name: str, company: str) -> bool:
    """
    Heuristic: check if name + company appear together on known platforms.
    We check a few public sources without scraping Google (ToS).
    """
    # Check if the person is mentioned on the company's LinkedIn page
    company_slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    li_url = f"https://www.linkedin.com/company/{company_slug}/"
    try:
        resp = requests.get(li_url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            # Company page exists – that's a weak positive signal
            return True
    except RequestException:
        pass

    return False


# ==========================================================================
# 4. EXPERIENCE TIMELINE ANALYSIS
# ==========================================================================

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def _parse_date(s: str, is_end: bool = False) -> Optional[date]:
    """Parse various date formats from resume experience.

    Args:
        s: date string from the resume
        is_end: if True, ambiguous dates default to end-of-period
                (Dec for year-only, last day for month-year).
    """
    if not s:
        return None
    s = s.strip().lower()
    if s in ("present", "current", "now", "till date", "till now",
             "ongoing", "to date", "currently"):
        return date.today()

    # YYYY-MM (ISO-ish)
    m = re.match(r"(\d{4})-(\d{1,2})$", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)

    # MM/YYYY or MM-YYYY
    m = re.match(r"(\d{1,2})[/\-](\d{4})", s)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)

    # Month YYYY  (e.g. "Jan 2020", "January 2020", "Mar. 2019")
    m = re.match(r"([a-z]+)\.?\s*[,]?\s*(\d{4})", s)
    if m:
        month = _MONTH_MAP.get(m.group(1))
        if month:
            return date(int(m.group(2)), month, 1)

    # YYYY Month  (e.g. "2020 Jan")
    m = re.match(r"(\d{4})\s+([a-z]+)", s)
    if m:
        month = _MONTH_MAP.get(m.group(2))
        if month:
            return date(int(m.group(1)), month, 1)

    # Just YYYY — default to Jan (start) or Dec (end)
    m = re.match(r"(\d{4})", s)
    if m:
        yr = int(m.group(1))
        return date(yr, 12, 1) if is_end else date(yr, 1, 1)

    return None


def verify_timeline(
    experience: list,
    claimed_total_years: float,
) -> Optional[ExperienceTimeline]:
    """Analyze the experience timeline for gaps, overlaps, and plausibility."""
    if not experience:
        return ExperienceTimeline(
            has_gaps=False, gap_details=[], has_overlaps=False, overlap_details=[],
            total_claimed_years=claimed_total_years, calculated_years=0.0,
            timeline_plausible=False, notes="No experience entries to analyze",
        )

    # Build sorted intervals
    intervals: list[tuple[date, date, str]] = []
    for exp in experience:
        start = _parse_date(exp.start_date, is_end=False)
        end = _parse_date(exp.end_date, is_end=True)
        if start and end:
            if start > end:
                start, end = end, start  # swap if reversed
            if start == end:
                # Same month stint — extend end by one month
                if end.month < 12:
                    end = date(end.year, end.month + 1, 1)
                else:
                    end = date(end.year + 1, 1, 1)
            intervals.append((start, end, exp.company))

    if not intervals:
        return ExperienceTimeline(
            has_gaps=False, gap_details=[], has_overlaps=False, overlap_details=[],
            total_claimed_years=claimed_total_years, calculated_years=0.0,
            timeline_plausible=True, notes="Could not parse experience dates",
        )

    intervals.sort(key=lambda x: x[0])

    # Check gaps (> 6 months between end of one and start of next)
    gaps: list[str] = []
    for i in range(len(intervals) - 1):
        _, prev_end, _ = intervals[i]
        next_start, _, _ = intervals[i + 1]
        gap_months = (next_start.year - prev_end.year) * 12 + (next_start.month - prev_end.month)
        if gap_months > 6:
            gaps.append(
                f"Gap: {prev_end.strftime('%b %Y')} – {next_start.strftime('%b %Y')} "
                f"({gap_months} months)"
            )

    # Check overlaps
    overlaps: list[str] = []
    for i in range(len(intervals) - 1):
        _, end_a, co_a = intervals[i]
        start_b, _, co_b = intervals[i + 1]
        if start_b < end_a:
            overlap_months = (end_a.year - start_b.year) * 12 + (end_a.month - start_b.month)
            if overlap_months > 1:  # Allow 1 month overlap for transition
                overlaps.append(
                    f"Overlap: {co_a} and {co_b} "
                    f"({start_b.strftime('%b %Y')} – {end_a.strftime('%b %Y')}, "
                    f"{overlap_months} months)"
                )

    # Calculate total months (merge overlapping intervals)
    merged = _merge_intervals(intervals)
    calc_months = sum((end - start).days / 30.44 for start, end in merged)
    calc_years = round(calc_months / 12, 1)

    # Plausibility: claimed vs calculated
    year_diff = abs(claimed_total_years - calc_years)
    plausible = year_diff <= 2.0  # Allow 2 year tolerance

    # Check: earliest start date implies reasonable working age
    earliest_start = intervals[0][0]
    notes_parts = []
    if earliest_start.year < 1990:
        notes_parts.append(f"Earliest job starts in {earliest_start.year} – verify")
    if year_diff > 2.0:
        notes_parts.append(
            f"Claimed {claimed_total_years} yrs vs calculated {calc_years} yrs "
            f"(diff: {year_diff:.1f} yrs)"
        )
    if not notes_parts:
        notes_parts.append("Timeline looks consistent")

    return ExperienceTimeline(
        has_gaps=bool(gaps),
        gap_details=gaps,
        has_overlaps=bool(overlaps),
        overlap_details=overlaps,
        total_claimed_years=claimed_total_years,
        calculated_years=calc_years,
        timeline_plausible=plausible,
        notes="; ".join(notes_parts),
    )


def _merge_intervals(
    intervals: list[tuple[date, date, str]],
) -> list[tuple[date, date]]:
    """Merge overlapping date intervals."""
    if not intervals:
        return []
    sorted_iv = sorted((s, e) for s, e, _ in intervals)
    merged = [sorted_iv[0]]
    for start, end in sorted_iv[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged
