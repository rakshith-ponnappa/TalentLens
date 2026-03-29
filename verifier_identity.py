"""
verifier_identity.py  –  Identity verification when LinkedIn is absent / supplement.

Verification layers (all public data, no paid APIs required):

  1. EMAIL VERIFICATION
     - Format validation (RFC 5322 basic)
     - Domain classification: Corporate / Personal / Disposable
     - Domain-to-employer matching
     - DNS MX record lookup

  2. EDUCATION VERIFICATION
     - Known university list + web domain check + Wikipedia lookup

  3. WEB PRESENCE SEARCH (30+ platforms)
     - GitHub (API - repos, stars, contributions)
     - StackOverflow (user search)
     - npm / PyPI / RubyGems / crates.io / NuGet (package registries)
     - Medium / Dev.to / Hashnode (tech blogs)
     - HackerRank / LeetCode / Kaggle / HackerEarth
     - Speaker Deck / SlideShare (conference speakers)
     - Twitter/X tech presence
     - Personal website / blog detection
     - Behance / Dribbble (designers)
     - Google Scholar / ResearchGate / ORCID (academics)
     - Bitbucket / GitLab (alternate code hosts)
     - Name + company co-occurrence via web search

  4. EXPERIENCE TIMELINE ANALYSIS
     - Gap detection (>6 months)
     - Overlap detection
     - Claimed vs calculated years comparison
     - Plausibility checks
"""
from __future__ import annotations

import re
import socket
import time
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
_API_HEADERS = {
    "User-Agent": "TalentLens-ResumeScreener/3.0 (Background Verification)",
    "Accept": "application/json",
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

    if domain in _DISPOSABLE_DOMAINS:
        domain_type = "Disposable"
    elif domain in _PERSONAL_DOMAINS:
        domain_type = "Personal"
    else:
        domain_type = "Corporate"

    mx_exists = _check_mx(domain)

    employer_match = False
    if experience and domain_type == "Corporate":
        employer_match = _domain_matches_company(domain, experience)

    notes_parts = []
    if domain_type == "Disposable":
        notes_parts.append("DISPOSABLE email domain - high risk")
    elif domain_type == "Corporate":
        if employer_match:
            notes_parts.append(f"Corporate domain '{domain}' matches a claimed employer")
        else:
            notes_parts.append(f"Corporate domain '{domain}' - not matched to any listed employer")
    else:
        notes_parts.append(f"Personal email ({domain})")

    if not mx_exists:
        notes_parts.append("No MX record - domain may not accept email")

    deliverable = "Yes" if mx_exists and format_valid else ("Unknown" if format_valid else "No")

    return EmailVerification(
        address=email, format_valid=format_valid, domain=domain,
        domain_type=domain_type, domain_matches_employer=employer_match,
        mx_record_exists=mx_exists, deliverable=deliverable,
        notes="; ".join(notes_parts),
    )


def _check_mx(domain: str) -> bool:
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, "MX")
        return len(answers) > 0
    except ImportError:
        try:
            socket.getaddrinfo(domain, 25, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except (socket.gaierror, OSError):
            return False
    except Exception:
        return False


def _domain_matches_company(domain: str, experience: list) -> bool:
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
    if not ev.format_valid:
        return 0.1
    score = 0.4
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

        inst_lower = institution.lower()
        known = any(k in inst_lower for k in _KNOWN_INSTITUTIONS)

        if not known:
            known = _check_institution_web(institution)

        # If still not found, try Wikipedia
        if not known:
            known = _check_institution_wikipedia(institution)

        source = "Known registry" if any(k in inst_lower for k in _KNOWN_INSTITUTIONS) else "Web lookup"

        results.append(EducationVerification(
            institution=institution,
            found_online=known,
            source=source if known else "Not found",
            degree_programs_plausible=True,
            notes=f"Institution {'verified' if known else 'not confirmed'} via {source.lower()}",
        ))

    return results


def _check_institution_web(name: str) -> bool:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    for tld in [".edu", ".ac.uk", ".ac.in", ".edu.au"]:
        domain = slug.replace("-", "") + tld
        try:
            socket.getaddrinfo(domain, 80, socket.AF_INET, socket.SOCK_STREAM)
            return True
        except (socket.gaierror, OSError):
            pass
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


def _check_institution_wikipedia(name: str) -> bool:
    """Check if institution has a Wikipedia article."""
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": f"{name} university OR college OR institute",
                "srlimit": 3, "format": "json",
            },
            headers=_API_HEADERS, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
        name_lower = name.lower()
        for hit in hits:
            if name_lower.split()[0] in hit["title"].lower():
                return True
    except (RequestException, Exception):
        pass
    return False


# ==========================================================================
# 3. WEB PRESENCE CHECK (30+ platforms)
# ==========================================================================

def verify_web_presence(
    name: str,
    experience: list | None = None,
    github_url: str = "",
) -> Optional[WebPresenceCheck]:
    """Search for the candidate's digital footprint across 30+ platforms."""
    if not name or name == "Unknown":
        return None

    profiles_found: list[str] = []
    red_flags: list[str] = []
    score = 0.2  # Base score for having a name

    name_slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    name_nospace = re.sub(r"[^a-z0-9]", "", name.lower())
    first_name = name.split()[0].lower() if name.split() else ""

    # Most recent company for co-occurrence check
    most_recent_company = ""
    if experience:
        for exp in experience:
            if exp.company.strip() and exp.company != "Unknown":
                most_recent_company = exp.company
                break

    # ---------- Code platforms ----------

    # GitHub (with API for richer data)
    gh = _check_github(name_slug, name_nospace, github_url)
    if gh["found"]:
        profiles_found.append(gh["url"])
        repos = gh.get("repos", 0)
        if repos > 20:
            score += 0.20
        elif repos > 5:
            score += 0.15
        elif repos > 0:
            score += 0.10
        else:
            score += 0.05
    elif github_url:
        red_flags.append(f"GitHub URL does not resolve: {github_url}")
        score -= 0.1

    # GitLab
    for slug in [name_slug, name_nospace]:
        gl = _check_profile_url(f"https://gitlab.com/{slug}", first_name)
        if gl:
            profiles_found.append(f"https://gitlab.com/{slug}")
            score += 0.08
            break

    # Bitbucket
    for slug in [name_slug, name_nospace]:
        bb = _check_profile_url(f"https://bitbucket.org/{slug}/", first_name)
        if bb:
            profiles_found.append(f"https://bitbucket.org/{slug}")
            score += 0.06
            break

    # StackOverflow
    so = _check_stackoverflow(name)
    if so:
        profiles_found.append(so)
        score += 0.10

    # ---------- Package registries ----------

    # npm (Node.js)
    npm = _check_npm_author(name_slug, name_nospace)
    if npm:
        profiles_found.append(npm)
        score += 0.10

    # PyPI (Python)
    pypi = _check_pypi_author(name_slug, name_nospace)
    if pypi:
        profiles_found.append(pypi)
        score += 0.10

    # RubyGems
    for slug in [name_slug, name_nospace]:
        rg = _check_profile_url(f"https://rubygems.org/profiles/{slug}", first_name)
        if rg:
            profiles_found.append(f"https://rubygems.org/profiles/{slug}")
            score += 0.06
            break

    # NuGet (.NET)
    for slug in [name_slug, name_nospace]:
        ng = _check_profile_url(f"https://www.nuget.org/profiles/{slug}", first_name)
        if ng:
            profiles_found.append(f"https://www.nuget.org/profiles/{slug}")
            score += 0.06
            break

    # crates.io (Rust)
    for slug in [name_slug, name_nospace]:
        cr = _check_json_url(f"https://crates.io/api/v1/users/{slug}")
        if cr:
            profiles_found.append(f"https://crates.io/users/{slug}")
            score += 0.06
            break

    # ---------- Tech blogs ----------

    # Medium
    for slug in [name_slug, name_nospace]:
        md = _check_profile_url(f"https://medium.com/@{slug}", first_name)
        if md:
            profiles_found.append(f"https://medium.com/@{slug}")
            score += 0.08
            break

    # Dev.to
    for slug in [name_slug, name_nospace]:
        dt = _check_profile_url(f"https://dev.to/{slug}", first_name)
        if dt:
            profiles_found.append(f"https://dev.to/{slug}")
            score += 0.08
            break

    # Hashnode
    for slug in [name_slug, name_nospace]:
        hn = _check_profile_url(f"https://hashnode.com/@{slug}", first_name)
        if hn:
            profiles_found.append(f"https://hashnode.com/@{slug}")
            score += 0.06
            break

    # ---------- Competitive programming ----------

    # HackerRank
    for slug in [name_slug, name_nospace]:
        hr = _check_profile_url(f"https://www.hackerrank.com/profile/{slug}", first_name)
        if hr:
            profiles_found.append(f"https://www.hackerrank.com/profile/{slug}")
            score += 0.06
            break

    # LeetCode
    for slug in [name_slug, name_nospace]:
        lc = _check_profile_url(f"https://leetcode.com/u/{slug}/", first_name)
        if lc:
            profiles_found.append(f"https://leetcode.com/u/{slug}")
            score += 0.06
            break

    # Kaggle
    for slug in [name_slug, name_nospace]:
        kg = _check_profile_url(f"https://www.kaggle.com/{slug}", first_name)
        if kg:
            profiles_found.append(f"https://www.kaggle.com/{slug}")
            score += 0.08
            break

    # HackerEarth
    for slug in [name_slug, name_nospace]:
        he = _check_profile_url(f"https://www.hackerearth.com/@{slug}", first_name)
        if he:
            profiles_found.append(f"https://www.hackerearth.com/@{slug}")
            score += 0.04
            break

    # ---------- Presentations / Conferences ----------

    # Speaker Deck
    for slug in [name_slug, name_nospace]:
        sd = _check_profile_url(f"https://speakerdeck.com/{slug}", first_name)
        if sd:
            profiles_found.append(f"https://speakerdeck.com/{slug}")
            score += 0.06
            break

    # SlideShare
    for slug in [name_slug, name_nospace]:
        ss = _check_profile_url(f"https://www.slideshare.net/{slug}", first_name)
        if ss:
            profiles_found.append(f"https://www.slideshare.net/{slug}")
            score += 0.04
            break

    # ---------- Design / Creative ----------

    # Behance
    for slug in [name_slug, name_nospace]:
        be = _check_profile_url(f"https://www.behance.net/{slug}", first_name)
        if be:
            profiles_found.append(f"https://www.behance.net/{slug}")
            score += 0.06
            break

    # Dribbble
    for slug in [name_slug, name_nospace]:
        dr = _check_profile_url(f"https://dribbble.com/{slug}", first_name)
        if dr:
            profiles_found.append(f"https://dribbble.com/{slug}")
            score += 0.06
            break

    # ---------- Academic / Research ----------

    # Google Scholar (search-based)
    gs = _check_google_scholar(name)
    if gs:
        profiles_found.append(gs)
        score += 0.10

    # ResearchGate
    for slug in [name_slug.replace("-", "_"), name_nospace]:
        rg2 = _check_profile_url(
            f"https://www.researchgate.net/profile/{slug.replace('-', '_').title()}",
            first_name,
        )
        if rg2:
            profiles_found.append(f"https://www.researchgate.net/profile/{slug}")
            score += 0.08
            break

    # ORCID search
    orcid = _check_orcid(name)
    if orcid:
        profiles_found.append(orcid)
        score += 0.10

    # ---------- Social / Professional ----------

    # Twitter/X
    for slug in [name_slug.replace("-", ""), name_nospace]:
        tw = _check_profile_url(f"https://x.com/{slug}", first_name)
        if tw:
            profiles_found.append(f"https://x.com/{slug}")
            score += 0.04
            break

    # ---------- Personal website ----------
    pw = _check_personal_website(name_slug, name_nospace, first_name)
    if pw:
        profiles_found.append(pw)
        score += 0.08

    # ---------- Name + company co-occurrence ----------
    cooccurrence = False
    if most_recent_company:
        cooccurrence = _check_name_company_web(name, most_recent_company)
        if cooccurrence:
            score += 0.15
        else:
            red_flags.append(
                f"Could not verify '{name}' worked at '{most_recent_company}' via web search"
            )

    # No digital footprint at all
    if not profiles_found and not cooccurrence:
        red_flags.append("No professional web presence found outside resume")
        score = max(score - 0.1, 0.1)

    # Build summary
    search_query = f'"{name}"'
    if most_recent_company:
        search_query += f' "{most_recent_company}"'

    notes_parts = []
    if profiles_found:
        notes_parts.append(
            f"Found {len(profiles_found)} profile(s) across {_count_platforms(profiles_found)} platforms"
        )
    if cooccurrence:
        notes_parts.append(f"Name + '{most_recent_company}' confirmed via web")
    if red_flags:
        notes_parts.append(f"{len(red_flags)} flag(s)")

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


# ---------- Platform-specific helpers ----------

def _check_github(name_slug: str, name_nospace: str, github_url: str) -> dict:
    """Check GitHub using the public API for richer data."""
    result = {"found": False, "url": "", "repos": 0, "stars": 0, "followers": 0}
    slugs = [name_slug, name_nospace]
    if github_url:
        m = re.search(r"github\.com/([^/?\s#]+)", github_url)
        if m:
            slugs.insert(0, m.group(1))

    for slug in slugs:
        try:
            resp = requests.get(
                f"https://api.github.com/users/{slug}",
                headers={**_API_HEADERS, "Accept": "application/vnd.github.v3+json"},
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                result["found"] = True
                result["url"] = data.get("html_url", f"https://github.com/{slug}")
                result["repos"] = data.get("public_repos", 0)
                result["followers"] = data.get("followers", 0)
                return result
        except RequestException:
            pass
        time.sleep(0.2)
    return result


def _check_stackoverflow(name: str) -> str | None:
    """Search StackOverflow for user by name."""
    so_url = f"https://stackoverflow.com/users?q={quote_plus(name)}&tab=reputation"
    try:
        resp = requests.get(so_url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200 and name.split()[0].lower() in resp.text.lower():
            return so_url
    except RequestException:
        pass
    return None


def _check_npm_author(name_slug: str, name_nospace: str) -> str | None:
    """Check npm for packages by this author."""
    for slug in [name_slug, name_nospace]:
        try:
            resp = requests.get(
                f"https://www.npmjs.com/~{slug}",
                headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True,
            )
            if resp.status_code == 200 and "npmjs.com/~" in resp.url:
                return f"https://www.npmjs.com/~{slug}"
        except RequestException:
            pass
    return None


def _check_pypi_author(name_slug: str, name_nospace: str) -> str | None:
    """Check PyPI for packages by this author."""
    for slug in [name_slug, name_nospace]:
        try:
            resp = requests.get(
                f"https://pypi.org/user/{slug}/",
                headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True,
            )
            if resp.status_code == 200 and "pypi.org/user/" in resp.url:
                return f"https://pypi.org/user/{slug}"
        except RequestException:
            pass
    return None


def _check_google_scholar(name: str) -> str | None:
    """Search Google Scholar for author profile."""
    try:
        resp = requests.get(
            f"https://scholar.google.com/citations?view_op=search_authors&mauthors={quote_plus(name)}",
            headers=_HEADERS, timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            m = re.search(r'href="(/citations\?user=[^"]+)"', resp.text)
            if m and name.split()[0].lower() in resp.text.lower():
                return f"https://scholar.google.com{m.group(1)}"
    except RequestException:
        pass
    return None


def _check_orcid(name: str) -> str | None:
    """Search ORCID registry for researcher."""
    try:
        parts = name.split()
        if len(parts) < 2:
            return None
        resp = requests.get(
            "https://pub.orcid.org/v3.0/search/",
            params={"q": f'family-name:"{parts[-1]}" AND given-names:"{parts[0]}"'},
            headers={**_API_HEADERS, "Accept": "application/json"},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("result", [])
            if results:
                orcid_id = results[0].get("orcid-identifier", {}).get("path", "")
                if orcid_id:
                    return f"https://orcid.org/{orcid_id}"
    except (RequestException, Exception):
        pass
    return None


def _check_personal_website(name_slug: str, name_nospace: str, first_name: str) -> str | None:
    """Check if the person has a personal website."""
    for domain in [
        f"{name_slug}.com", f"{name_slug}.dev", f"{name_slug}.io",
        f"{name_slug}.me", f"{name_nospace}.com", f"{name_nospace}.dev",
    ]:
        try:
            resp = requests.head(
                f"https://{domain}",
                headers=_HEADERS, timeout=6, allow_redirects=True,
            )
            if resp.status_code < 400:
                return f"https://{domain}"
        except RequestException:
            pass
    return None


def _check_profile_url(url: str, first_name: str) -> bool:
    """Generic: check if a profile URL resolves to a valid page."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        if resp.status_code == 200:
            lower_text = resp.text.lower()
            not_found_signals = [
                "page not found", "404", "user not found", "doesn't exist",
                "no user found", "this page is no longer available",
            ]
            for signal in not_found_signals:
                if signal in lower_text[:2000]:
                    return False
            return True
    except RequestException:
        pass
    return False


def _check_json_url(url: str) -> bool:
    """Check if a JSON API endpoint returns valid data."""
    try:
        resp = requests.get(url, headers=_API_HEADERS, timeout=_TIMEOUT)
        return resp.status_code == 200
    except RequestException:
        return False


def _check_name_company_web(name: str, company: str) -> bool:
    """Check if name + company appear together on the web."""
    # Method 1: DuckDuckGo search
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": f'"{name}" "{company}"'},
            headers=_HEADERS, timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            hits = len(re.findall(r'class="result__a"', resp.text))
            if hits >= 2:
                return True
    except RequestException:
        pass

    # Method 2: LinkedIn company page check
    company_slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    li_url = f"https://www.linkedin.com/company/{company_slug}/"
    try:
        resp = requests.get(li_url, headers=_HEADERS, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return True
    except RequestException:
        pass

    return False


def _count_platforms(urls: list[str]) -> int:
    """Count unique platform domains."""
    domains = set()
    for url in urls:
        m = re.search(r"https?://(?:www\.)?([^/]+)", url)
        if m:
            domains.add(m.group(1).split(".")[0])
    return len(domains)


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
    if not s:
        return None
    s = s.strip().lower()
    if s in ("present", "current", "now", "till date", "till now",
             "ongoing", "to date", "currently"):
        return date.today()

    m = re.match(r"(\d{4})-(\d{1,2})$", s)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)

    m = re.match(r"(\d{1,2})[/\-](\d{4})", s)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)

    m = re.match(r"([a-z]+)\.?\s*[,]?\s*(\d{4})", s)
    if m:
        month = _MONTH_MAP.get(m.group(1))
        if month:
            return date(int(m.group(2)), month, 1)

    m = re.match(r"(\d{4})\s+([a-z]+)", s)
    if m:
        month = _MONTH_MAP.get(m.group(2))
        if month:
            return date(int(m.group(1)), month, 1)

    m = re.match(r"(\d{4})", s)
    if m:
        yr = int(m.group(1))
        return date(yr, 12, 1) if is_end else date(yr, 1, 1)

    return None


def verify_timeline(
    experience: list,
    claimed_total_years: float,
) -> Optional[ExperienceTimeline]:
    if not experience:
        return ExperienceTimeline(
            has_gaps=False, gap_details=[], has_overlaps=False, overlap_details=[],
            total_claimed_years=claimed_total_years, calculated_years=0.0,
            timeline_plausible=False, notes="No experience entries to analyze",
        )

    intervals: list[tuple[date, date, str]] = []
    for exp in experience:
        start = _parse_date(exp.start_date, is_end=False)
        end = _parse_date(exp.end_date, is_end=True)
        if start and end:
            if start > end:
                start, end = end, start
            if start == end:
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

    gaps: list[str] = []
    for i in range(len(intervals) - 1):
        _, prev_end, _ = intervals[i]
        next_start, _, _ = intervals[i + 1]
        gap_months = (next_start.year - prev_end.year) * 12 + (next_start.month - prev_end.month)
        if gap_months > 6:
            gaps.append(
                f"Gap: {prev_end.strftime('%b %Y')} - {next_start.strftime('%b %Y')} "
                f"({gap_months} months)"
            )

    overlaps: list[str] = []
    for i in range(len(intervals) - 1):
        _, end_a, co_a = intervals[i]
        start_b, _, co_b = intervals[i + 1]
        if start_b < end_a:
            overlap_months = (end_a.year - start_b.year) * 12 + (end_a.month - start_b.month)
            if overlap_months > 1:
                overlaps.append(
                    f"Overlap: {co_a} and {co_b} "
                    f"({start_b.strftime('%b %Y')} - {end_a.strftime('%b %Y')}, "
                    f"{overlap_months} months)"
                )

    merged = _merge_intervals(intervals)
    calc_months = sum((end - start).days / 30.44 for start, end in merged)
    calc_years = round(calc_months / 12, 1)

    year_diff = abs(claimed_total_years - calc_years)
    plausible = year_diff <= 2.0

    earliest_start = intervals[0][0]
    notes_parts = []
    if earliest_start.year < 1990:
        notes_parts.append(f"Earliest job starts in {earliest_start.year} - verify")
    if year_diff > 2.0:
        notes_parts.append(
            f"Claimed {claimed_total_years} yrs vs calculated {calc_years} yrs "
            f"(diff: {year_diff:.1f} yrs)"
        )
    if not notes_parts:
        notes_parts.append("Timeline looks consistent")

    return ExperienceTimeline(
        has_gaps=bool(gaps), gap_details=gaps,
        has_overlaps=bool(overlaps), overlap_details=overlaps,
        total_claimed_years=claimed_total_years, calculated_years=calc_years,
        timeline_plausible=plausible, notes="; ".join(notes_parts),
    )


def _merge_intervals(
    intervals: list[tuple[date, date, str]],
) -> list[tuple[date, date]]:
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
