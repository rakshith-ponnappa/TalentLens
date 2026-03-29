"""
verifier_company.py  –  Verify whether companies listed on a resume are legitimate.

Multi-layer online verification (no paid API keys required):

  Layer 1: Known Companies DB      – instant local lookup (58+ entries)
  Layer 2: OpenCorporates API      – company registration data, jurisdiction, status
  Layer 3: LinkedIn company page   – employee count, existence
  Layer 4: Wikipedia / Wikidata    – encyclopaedia entries confirm major companies
  Layer 5: GitHub organization     – tech companies usually have GitHub orgs
  Layer 6: Company domain check    – resolve companyname.com, check TLS cert age
  Layer 7: Glassdoor / Indeed      – job postings confirm active employers
  Layer 8: DuckDuckGo search       – catch-all web presence confirmation
  Layer 9: Crunchbase (public)     – startup funding & existence data

Legitimacy score (0.0 – 1.0) is computed from all signals combined.
"""
from __future__ import annotations

import json
import re
import ssl
import socket
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

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
_API_HEADERS = {
    "User-Agent": "TalentLens-ResumeScreener/3.0 (Background Verification)",
    "Accept": "application/json",
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
    lower = name.lower().strip().rstrip(".")
    for key, info in _KNOWN_COMPANIES.items():
        if key in lower or lower in key:
            return _known_to_verification(name, info)
        for alias in info.get("aliases", []):
            if alias in lower or lower in alias:
                return _known_to_verification(name, info)
        if info["full_name"].lower() in lower or lower in info["full_name"].lower():
            return _known_to_verification(name, info)
    return None


def _known_to_verification(original_name: str, info: dict) -> CompanyVerification:
    return CompanyVerification(
        name=info["full_name"],
        found=True,
        source="Known Companies DB",
        employee_count=info.get("employee_count", "Unknown"),
        company_type=info.get("type", "Unknown"),
        founded_year=info.get("founded"),
        status=info.get("status", "Active"),
        legitimacy_score=1.0,
        notes=(
            f"Verified via known companies database. HQ: {info.get('hq', 'N/A')}. "
            f"{'Public ('+info.get('ticker', '')+')' if info.get('public') else 'Private'}"
        ),
    )


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def verify_company(name: str, api_key: str = "") -> CompanyVerification:
    """Run ALL online checks and return a CompanyVerification result."""
    if not name.strip():
        return _unknown(name, "Empty company name")

    # Layer 1: Known companies DB (instant)
    known = _lookup_known(name)
    if known:
        return known

    # Layers 2-9: Online verification cascade
    score = 0.0
    notes_parts: list[str] = []
    sources_found: list[str] = []
    emp = None
    founded = None

    # Layer 2: OpenCorporates
    oc = _check_opencorporates(name, api_key)
    if oc["found"]:
        score += 0.20
        sources_found.append("OpenCorporates")
        if oc["status"].lower() == "active":
            score += 0.10
        notes_parts.append(f"OC: {oc['jurisdiction']} - {oc['status']}")
        emp = oc.get("employee_count")
        founded = oc.get("founded_year")

    # Layer 3: LinkedIn company page
    li = _check_linkedin_page(name)
    if li["exists"]:
        score += 0.15
        sources_found.append("LinkedIn")
        notes_parts.append("LinkedIn company page found")
        emp = emp or li.get("employee_count")

    # Layer 4: Wikipedia / Wikidata
    wiki = _check_wikipedia(name)
    if wiki["found"]:
        score += 0.15
        sources_found.append("Wikipedia")
        if wiki.get("description"):
            notes_parts.append(f"Wikipedia: {wiki['description'][:80]}")
        emp = emp or wiki.get("employee_count")
        founded = founded or wiki.get("founded_year")

    # Layer 5: GitHub organization
    gh = _check_github_org(name)
    if gh["found"]:
        score += 0.10
        sources_found.append("GitHub")
        notes_parts.append(f"GitHub org: {gh.get('repos', 0)} repos")

    # Layer 6: Company domain check
    domain = _check_company_domain(name)
    if domain["resolves"]:
        score += 0.10
        sources_found.append("Company Website")
        tls = domain.get("tls_years")
        notes_parts.append(f"Domain active{f', TLS age ~{tls}y' if tls else ''}")

    # Layer 7: Job boards
    jobs = _check_job_boards(name)
    if jobs["found"]:
        score += 0.08
        sources_found.append("Job Boards")
        notes_parts.append(f"Active on {jobs.get('source', 'job boards')}")

    # Layer 8: DuckDuckGo (catch-all, only if sparse results)
    if not sources_found:
        ddg = _check_duckduckgo(name)
        if ddg["found"]:
            score += 0.12
            sources_found.append("Web Search")
            notes_parts.append(f"Web search: {ddg.get('hits', 0)} results")

    # Layer 9: Crunchbase (if still low confidence)
    if score < 0.5:
        cb = _check_crunchbase(name)
        if cb["found"]:
            score += 0.10
            sources_found.append("Crunchbase")
            notes_parts.append(f"Crunchbase: {cb.get('description', 'found')[:60]}")

    # Aggregate
    emp = emp or "Unknown"
    if founded and 1800 < int(founded) < 2030:
        score += 0.05
    if emp and emp != "Unknown":
        score += 0.05

    found = bool(sources_found)
    if not found:
        notes_parts.append("Not found on any online source - may be fictitious or very small")

    return CompanyVerification(
        name=name,
        found=found,
        source=", ".join(sources_found) if sources_found else "Not found",
        employee_count=_employee_bucket(emp),
        company_type=_classify_company(emp, founded),
        founded_year=founded,
        status=oc.get("status", "Unknown") if oc["found"] else "Unknown",
        legitimacy_score=round(min(score, 1.0), 2),
        notes="; ".join(notes_parts) if notes_parts else "No verification data",
    )


def verify_companies(names: list[str], api_key: str = "") -> list[CompanyVerification]:
    results = []
    for name in names:
        results.append(verify_company(name, api_key))
        time.sleep(0.3)
    return results


# ==========================================================================
# Layer 2: OpenCorporates
# ==========================================================================

def _check_opencorporates(name: str, api_key: str) -> dict:
    result = {"found": False, "status": "Unknown", "jurisdiction": "",
              "founded_year": None, "employee_count": None}
    try:
        params: dict = {"q": name, "format": "json", "per_page": 1}
        if api_key:
            params["api_token"] = api_key
        resp = requests.get(
            f"{_OPENCORP_BASE}/companies/search",
            params=params, headers=_HEADERS, timeout=_TIMEOUT,
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
    except (RequestException, Exception):
        pass
    return result


# ==========================================================================
# Layer 3: LinkedIn company page
# ==========================================================================

def _check_linkedin_page(company_name: str) -> dict:
    result = {"exists": False, "employee_count": None, "founded_year": None}
    slug = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    url = f"https://www.linkedin.com/company/{slug}/"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        if resp.status_code == 200 and "authwall" not in resp.url:
            result["exists"] = True
            emp_match = re.search(r'"employeeCount"\s*:\s*(\d+)', resp.text)
            if emp_match:
                result["employee_count"] = emp_match.group(1)
    except RequestException:
        pass
    return result


# ==========================================================================
# Layer 4: Wikipedia / Wikidata API (free, no auth)
# ==========================================================================

def _check_wikipedia(company_name: str) -> dict:
    result = {"found": False, "description": "", "founded_year": None, "employee_count": None}
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "list": "search",
                "srsearch": f"{company_name} company",
                "srlimit": 3, "format": "json",
            },
            headers=_API_HEADERS, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
        if not hits:
            return result

        name_lower = company_name.lower()
        best_title = None
        for hit in hits:
            tl = hit["title"].lower()
            if name_lower in tl or tl in name_lower or _company_name_match(name_lower, tl):
                best_title = hit["title"]
                break
        if not best_title:
            snippet = hits[0].get("snippet", "").lower()
            if name_lower.split()[0] in snippet:
                best_title = hits[0]["title"]
        if not best_title:
            return result

        result["found"] = True

        # Get extract
        resp2 = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query", "titles": best_title,
                "prop": "extracts", "exintro": True, "exsentences": 3,
                "explaintext": True, "format": "json",
            },
            headers=_API_HEADERS, timeout=_TIMEOUT,
        )
        resp2.raise_for_status()
        for page in resp2.json().get("query", {}).get("pages", {}).values():
            extract = page.get("extract", "")
            if extract:
                result["description"] = extract[:200]
                m = re.search(r"(?:founded|established|incorporated)\s+(?:in\s+)?(\d{4})", extract, re.I)
                if m:
                    result["founded_year"] = int(m.group(1))
                m = re.search(r"([\d,]+)\s*employees", extract, re.I)
                if m:
                    result["employee_count"] = m.group(1).replace(",", "")
    except (RequestException, Exception):
        pass

    # Wikidata structured data backup
    if result["found"] and (not result["founded_year"] or not result["employee_count"]):
        wd = _check_wikidata(company_name)
        result["founded_year"] = result["founded_year"] or wd.get("founded_year")
        result["employee_count"] = result["employee_count"] or wd.get("employee_count")

    return result


def _check_wikidata(company_name: str) -> dict:
    result = {"founded_year": None, "employee_count": None}
    try:
        resp = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities", "search": company_name,
                "language": "en", "limit": 3, "format": "json",
            },
            headers=_API_HEADERS, timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        results = resp.json().get("search", [])
        if not results:
            return result
        entity_id = results[0]["id"]

        resp2 = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetclaims", "entity": entity_id,
                "property": "P571|P1128", "format": "json",
            },
            headers=_API_HEADERS, timeout=_TIMEOUT,
        )
        resp2.raise_for_status()
        claims = resp2.json().get("claims", {})
        if "P571" in claims and claims["P571"]:
            try:
                timestr = claims["P571"][0]["mainsnak"]["datavalue"]["value"]["time"]
                m = re.search(r"(\d{4})", timestr)
                if m:
                    result["founded_year"] = int(m.group(1))
            except (KeyError, IndexError):
                pass
        if "P1128" in claims and claims["P1128"]:
            try:
                amount = claims["P1128"][-1]["mainsnak"]["datavalue"]["value"]["amount"]
                result["employee_count"] = str(int(float(amount.lstrip("+"))))
            except (KeyError, IndexError, ValueError):
                pass
    except (RequestException, Exception):
        pass
    return result


def _company_name_match(name: str, title: str) -> bool:
    for suffix in [" inc", " ltd", " llc", " plc", " corp", " corporation",
                   " limited", " technologies", " technology", " systems",
                   " services", " solutions", " group", " holdings"]:
        name = name.replace(suffix, "")
        title = title.replace(suffix, "")
    name_words = set(name.split())
    title_words = set(title.split())
    if not name_words:
        return False
    return len(name_words & title_words) >= max(1, len(name_words) * 0.5)


# ==========================================================================
# Layer 5: GitHub organization
# ==========================================================================

def _check_github_org(company_name: str) -> dict:
    result = {"found": False, "repos": 0, "members": "N/A", "url": ""}
    for slug in _company_to_github_slugs(company_name):
        try:
            resp = requests.get(
                f"https://api.github.com/orgs/{slug}",
                headers={**_API_HEADERS, "Accept": "application/vnd.github.v3+json"},
                timeout=_TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                result["found"] = True
                result["repos"] = data.get("public_repos", 0)
                result["url"] = data.get("html_url", "")
                return result
        except RequestException:
            pass
        time.sleep(0.2)
    return result


def _company_to_github_slugs(name: str) -> list[str]:
    base = re.sub(r"[^a-z0-9]+", "", name.lower())
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slugs = [base, slug]
    for suffix in ["inc", "ltd", "llc", "plc", "corp", "limited",
                    "technologies", "technology", "software", "labs",
                    "solutions", "services", "systems", "group"]:
        trimmed = re.sub(rf"\s*{suffix}\s*$", "", name.lower()).strip()
        t_slug = re.sub(r"[^a-z0-9]+", "-", trimmed).strip("-")
        t_base = re.sub(r"[^a-z0-9]+", "", trimmed)
        for s in [t_slug, t_base]:
            if s not in slugs:
                slugs.append(s)
    return slugs[:5]


# ==========================================================================
# Layer 6: Company domain check + TLS cert age
# ==========================================================================

def _check_company_domain(company_name: str) -> dict:
    result = {"resolves": False, "domain": "", "tls_years": None}
    for domain in _company_to_domain_slugs(company_name):
        try:
            resp = requests.head(
                f"https://www.{domain}",
                headers=_HEADERS, timeout=8, allow_redirects=True,
            )
            if resp.status_code < 400:
                result["resolves"] = True
                result["domain"] = domain
                result["tls_years"] = _get_tls_cert_age(domain)
                return result
        except RequestException:
            pass
    return result


def _company_to_domain_slugs(name: str) -> list[str]:
    base = re.sub(r"[^a-z0-9]+", "", name.lower())
    for suffix in ["inc", "ltd", "llc", "plc", "corp", "limited",
                    "technologies", "technology", "solutions", "services",
                    "systems", "group", "holdings"]:
        base = re.sub(rf"{suffix}$", "", base)
    domains = []
    for tld in [".com", ".io", ".co", ".org", ".net"]:
        d = base + tld
        if d not in domains:
            domains.append(d)
    return domains[:6]


def _get_tls_cert_age(domain: str) -> int | None:
    try:
        ctx = ssl.create_default_context()
        with ctx.wrap_socket(socket.socket(), server_hostname=domain) as s:
            s.settimeout(5)
            s.connect((domain, 443))
            cert = s.getpeercert()
            not_before = datetime.strptime(cert["notBefore"], "%b %d %H:%M:%S %Y %Z")
            return max(0, (datetime.now() - not_before).days // 365)
    except Exception:
        return None


# ==========================================================================
# Layer 7: Job boards
# ==========================================================================

def _check_job_boards(company_name: str) -> dict:
    result = {"found": False, "source": ""}
    slug = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    # Glassdoor
    try:
        resp = requests.get(
            f"https://www.glassdoor.com/Overview/Working-at-{slug}-EI_IE.htm",
            headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True,
        )
        if resp.status_code == 200 and company_name.split()[0].lower() in resp.text.lower():
            result["found"] = True
            result["source"] = "Glassdoor"
            return result
    except RequestException:
        pass
    # Indeed
    try:
        resp = requests.get(
            f"https://www.indeed.com/cmp/{slug}",
            headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True,
        )
        if resp.status_code == 200 and "indeed.com/cmp" in resp.url:
            result["found"] = True
            result["source"] = "Indeed"
            return result
    except RequestException:
        pass
    return result


# ==========================================================================
# Layer 8: DuckDuckGo search (catch-all)
# ==========================================================================

def _check_duckduckgo(company_name: str) -> dict:
    result = {"found": False, "hits": 0}
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": f'"{company_name}" company'},
            headers=_HEADERS, timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            hits = len(re.findall(r'class="result__a"', resp.text))
            if hits > 0 and company_name.split()[0].lower() in resp.text.lower():
                result["found"] = True
                result["hits"] = hits
    except RequestException:
        pass
    return result


# ==========================================================================
# Layer 9: Crunchbase
# ==========================================================================

def _check_crunchbase(company_name: str) -> dict:
    result = {"found": False, "description": ""}
    slug = re.sub(r"[^a-z0-9]+", "-", company_name.lower()).strip("-")
    try:
        resp = requests.get(
            f"https://www.crunchbase.com/organization/{slug}",
            headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True,
        )
        if resp.status_code == 200 and "crunchbase.com/organization" in resp.url:
            m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', resp.text, re.I)
            if m:
                result["description"] = m.group(1)[:150]
            result["found"] = True
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


def _unknown(name: str, reason: str) -> CompanyVerification:
    return CompanyVerification(
        name=name, found=False, source="", employee_count="Unknown",
        company_type="Unknown", founded_year=None, status="Unknown",
        legitimacy_score=0.0, notes=reason,
    )
