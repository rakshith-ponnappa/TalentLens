"""
verifier/company.py  –  Verify whether companies listed on a resume are legitimate.

Sources used (no auth needed for basic checks):
  1. OpenCorporates public API   (company registration data, jurisdiction, status)
  2. LinkedIn public company page (employee count hint, existence)
  3. Google/SerpAPI              (optional, for fallback web presence check)

Legitimacy score heuristic:
  - Found on OpenCorporates (+0.4)
  - Status = Active (+0.2)
  - LinkedIn page exists (+0.2)
  - Detectable employee count (+0.1)
  - Founding year plausible (+0.1)
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests
from requests.exceptions import RequestException

from models import CompanyVerification


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_OPENCORP_BASE = "https://api.opencorporates.com/v0.4"
_TIMEOUT = 10


# --------------------------------------------------------------------------
# Known companies database (loaded once)
# --------------------------------------------------------------------------

def _load_known_companies() -> dict:
    p = Path(__file__).parent / "data" / "known_companies.json"
    if p.exists():
        return json.loads(p.read_text()).get("companies", {})
    return {}

_KNOWN_COMPANIES: dict = _load_known_companies()


def _lookup_known(name: str) -> CompanyVerification | None:
    """Check company name against the known companies database."""
    lower = name.lower().strip().rstrip('.')
    # Direct key match
    for key, info in _KNOWN_COMPANIES.items():
        if key in lower or lower in key:
            return _known_to_verification(name, info)
        # Check aliases
        for alias in info.get("aliases", []):
            if alias in lower or lower in alias:
                return _known_to_verification(name, info)
        # Check full name
        if info["full_name"].lower() in lower or lower in info["full_name"].lower():
            return _known_to_verification(name, info)
    return None


def _known_to_verification(original_name: str, info: dict) -> CompanyVerification:
    """Convert a known company entry to a CompanyVerification result."""
    return CompanyVerification(
        name=info["full_name"],
        found=True,
        source="Known Companies DB",
        employee_count=info.get("employee_count", "Unknown"),
        company_type=info.get("type", "Unknown"),
        founded_year=info.get("founded"),
        status=info.get("status", "Active"),
        legitimacy_score=1.0,
        notes=f"Verified via known companies database. HQ: {info.get('hq', 'N/A')}. "
              f"{'Public ('+info.get('ticker', '')+')' if info.get('public') else 'Private'}",
    )


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def verify_company(name: str, api_key: str = "") -> CompanyVerification:
    """Run all checks and return a CompanyVerification result."""
    if not name.strip():
        return _unknown(name, "Empty company name")

    # 1. Check known companies database first (instant, no API call)
    known = _lookup_known(name)
    if known:
        return known

    # 2. Fall back to OpenCorporates + LinkedIn
    oc = _check_opencorporates(name, api_key)
    li = _check_linkedin_page(name)

    score = 0.0
    notes_parts = []

    if oc["found"]:
        score += 0.4
        if oc["status"].lower() == "active":
            score += 0.2
        notes_parts.append(f"OC: {oc['jurisdiction']} – {oc['status']}")
    else:
        notes_parts.append("Not found on OpenCorporates")

    if li["exists"]:
        score += 0.2
        notes_parts.append("LinkedIn page found")
    else:
        notes_parts.append("LinkedIn page not found")

    if oc.get("employee_count") or li.get("employee_count"):
        score += 0.1

    emp = oc.get("employee_count") or li.get("employee_count") or "Unknown"
    founded = oc.get("founded_year") or li.get("founded_year")

    if founded and 1800 < int(founded) < 2030:
        score += 0.1

    company_type = _classify_company(emp, founded)

    return CompanyVerification(
        name=name,
        found=oc["found"] or li["exists"],
        source=_source_label(oc["found"], li["exists"]),
        employee_count=_employee_bucket(emp),
        company_type=company_type,
        founded_year=founded,
        status=oc.get("status", "Unknown"),
        legitimacy_score=round(min(score, 1.0), 2),
        notes="; ".join(notes_parts),
    )


def verify_companies(names: list[str], api_key: str = "") -> list[CompanyVerification]:
    results = []
    for name in names:
        results.append(verify_company(name, api_key))
        time.sleep(0.5)  # polite rate-limiting
    return results


# --------------------------------------------------------------------------
# OpenCorporates
# --------------------------------------------------------------------------

def _check_opencorporates(name: str, api_key: str) -> dict:
    result = {"found": False, "status": "Unknown", "jurisdiction": "", "founded_year": None, "employee_count": None}
    try:
        params: dict = {"q": name, "format": "json", "per_page": 1}
        if api_key:
            params["api_token"] = api_key
        resp = requests.get(
            f"{_OPENCORP_BASE}/companies/search",
            params=params,
            headers=_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        companies = data.get("results", {}).get("companies", [])
        if companies:
            co = companies[0].get("company", {})
            result["found"] = True
            result["status"] = co.get("current_status") or "Unknown"
            result["jurisdiction"] = co.get("jurisdiction_code", "")
            inc_date = co.get("incorporation_date", "")
            if inc_date:
                m = re.search(r"(\d{4})", inc_date)
                result["founded_year"] = int(m.group(1)) if m else None
    except RequestException:
        pass  # network error – treated as not found
    except Exception:
        pass
    return result


# --------------------------------------------------------------------------
# LinkedIn public company page
# --------------------------------------------------------------------------

def _check_linkedin_page(company_name: str) -> dict:
    """
    Attempt to verify company existence via a public LinkedIn company search
    URL.  Does NOT require authentication.
    Note: LinkedIn may block scraping – we only check HTTP status, 
    not parse content, to stay within fair use.
    """
    result = {"exists": False, "employee_count": None, "founded_year": None}
    slug = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    url = f"https://www.linkedin.com/company/{slug}/"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        # LinkedIn returns 200 for valid company pages even without auth
        if resp.status_code == 200 and "authwall" not in resp.url:
            result["exists"] = True
            # Try to extract employee count from meta/script tags
            emp_match = re.search(r'"employeeCount"\s*:\s*(\d+)', resp.text)
            if emp_match:
                result["employee_count"] = emp_match.group(1)
    except RequestException:
        pass
    return result


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _classify_company(emp_str: str, founded_year) -> str:
    emp_str = str(emp_str or "")
    try:
        count = int(re.sub(r"[^0-9]", "", emp_str) or "0")
    except ValueError:
        count = 0

    if count == 0:
        return "Unknown"
    if count < 11:
        return "Micro (1-10)"
    if count < 51:
        return "Startup (11-50)"
    if count < 201:
        return "SME (51-200)"
    if count < 1001:
        return "Mid-size (201-1000)"
    if count < 10001:
        return "Enterprise (1001-10000)"
    return "Large Enterprise (10000+)"


def _employee_bucket(emp) -> str:
    if not emp or emp == "Unknown":
        return "Unknown"
    try:
        n = int(re.sub(r"[^0-9]", "", str(emp)) or "0")
    except ValueError:
        return str(emp)
    for lo, hi, label in [
        (1, 10, "1-10"), (11, 50, "11-50"), (51, 200, "51-200"),
        (201, 500, "201-500"), (501, 1000, "501-1000"), (1001, 5000, "1001-5000"),
        (5001, 10000, "5001-10000"),
    ]:
        if lo <= n <= hi:
            return label
    return "10000+"


def _source_label(oc_found: bool, li_found: bool) -> str:
    sources = []
    if oc_found:
        sources.append("OpenCorporates")
    if li_found:
        sources.append("LinkedIn")
    return ", ".join(sources) if sources else "Not found"


def _unknown(name: str, reason: str) -> CompanyVerification:
    return CompanyVerification(
        name=name, found=False, source="", employee_count="Unknown",
        company_type="Unknown", founded_year=None, status="Unknown",
        legitimacy_score=0.0, notes=reason,
    )
