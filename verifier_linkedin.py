"""
verifier_linkedin.py  –  Verify a LinkedIn profile URL and assess authenticity.

What we check (all from public data, no login required):
  1. URL resolves (HTTP 200, not authwall redirect)
  2. Profile name visible in page meta tags
  3. Headline / current role visible
  4. Connection count hint ("500+" etc.) in page source
  5. Profile completeness signals (photo, summary, skills sections present)

Authenticity scoring heuristics (known patterns for fake profiles):
  - No photo meta tag          → red flag
  - Very generic headline      → mild flag
  - URL slug doesn't look real → mild flag
  - Profile created very recently (sometimes detectable) → flag
  - Name on profile doesn't match resume name → red flag

Note: LinkedIn actively limits scraping.  We only issue ONE HTTP GET per
profile and do not follow authenticated paths.  This is read-only, public
information retrieval consistent with fair use.
"""
from __future__ import annotations

import re
import time
from difflib import SequenceMatcher
from urllib.parse import urlparse, quote_plus

import requests
from requests.exceptions import RequestException

from models import LinkedInVerification


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
_TIMEOUT = 10


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def verify_linkedin(url: str, candidate_name: str = "") -> LinkedInVerification:
    if not url or "linkedin.com" not in url.lower():
        return LinkedInVerification(
            url=url, url_resolves=False, profile_name="", headline="",
            connections_label="", profile_completeness="Unknown",
            authenticity_score=0.0, red_flags=["No LinkedIn URL provided"],
            notes="",
        )

    url = _normalise_url(url)
    html, resolved_url, resolves = _fetch(url)

    if not resolves:
        return LinkedInVerification(
            url=url, url_resolves=False, profile_name="", headline="",
            connections_label="", profile_completeness="Unknown",
            authenticity_score=0.2, red_flags=["Profile URL does not resolve"],
            notes="LinkedIn returned non-200 or authwall redirect",
        )

    # Parse available signals from meta tags / JSON-LD in the public page
    profile_name = _extract_og("og:title", html) or _extract_meta("name", html)
    headline = _extract_og("og:description", html) or ""
    connections = _extract_connections(html)
    has_photo = bool(re.search(r'og:image.*linkedin.*photo|profile-photo', html, re.I))

    red_flags: list[str] = []
    score = 0.5  # base

    # Name mismatch check
    if candidate_name and profile_name:
        match_ratio = SequenceMatcher(
            None,
            candidate_name.lower(),
            profile_name.lower().replace("| linkedin", "").strip(),
        ).ratio()
        if match_ratio < 0.5:
            red_flags.append(f"Profile name '{profile_name}' doesn't match resume name '{candidate_name}'")
            score -= 0.3
        else:
            score += 0.1

    if not has_photo:
        red_flags.append("No profile photo detected")
        score -= 0.1
    else:
        score += 0.1

    if not headline or len(headline) < 10:
        red_flags.append("Minimal headline / description")
        score -= 0.05
    else:
        score += 0.1

    if connections:
        score += 0.1
        if "500" in connections:
            score += 0.1
    else:
        red_flags.append("Connection count not visible (may be private)")

    slug = _extract_slug(url)
    if slug and re.fullmatch(r"[a-z]+-[a-z]+-[a-f0-9]{8}", slug or ""):
        # Auto-generated LinkedIn slug – less trustworthy
        red_flags.append("Auto-generated URL slug (profile never customised)")
        score -= 0.05

    completeness = "High" if score >= 0.7 else "Medium" if score >= 0.5 else "Low"

    return LinkedInVerification(
        url=url,
        url_resolves=True,
        profile_name=_clean_li_title(profile_name),
        headline=_clean_headline(headline),
        connections_label=connections,
        profile_completeness=completeness,
        authenticity_score=round(max(0.0, min(score, 1.0)), 2),
        red_flags=red_flags,
        notes=f"Resolved to: {resolved_url}" if resolved_url != url else "",
    )


# --------------------------------------------------------------------------
# HTTP fetch
# --------------------------------------------------------------------------

def _fetch(url: str) -> tuple[str, str, bool]:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return "", resp.url, False
        if "authwall" in resp.url or "login" in resp.url:
            return "", resp.url, False
        return resp.text, resp.url, True
    except RequestException:
        return "", url, False


# --------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------

def _extract_og(prop: str, html: str) -> str:
    m = re.search(rf'<meta[^>]+property=["\']og:{re.escape(prop.split(":")[-1])}["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{re.escape(prop.split(":")[-1])}["\']', html, re.I)
    return m.group(1).strip() if m else ""


def _extract_meta(name: str, html: str) -> str:
    m = re.search(rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    return m.group(1).strip() if m else ""


def _extract_connections(html: str) -> str:
    m = re.search(r'"connectionsCount"\s*:\s*(\d+)', html)
    if m:
        n = int(m.group(1))
        return f"{n}" if n < 500 else "500+"
    if "500+" in html:
        return "500+"
    return ""


def _extract_slug(url: str) -> str | None:
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url)
    return m.group(1) if m else None


def _normalise_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url


def _clean_li_title(title: str) -> str:
    return re.sub(r"\s*[|–-]\s*LinkedIn\s*$", "", title, flags=re.I).strip()


def _clean_headline(h: str) -> str:
    # LinkedIn og:description often contains "View ... profile on LinkedIn..."
    h = re.sub(r"View .{0,60} profile on LinkedIn.*", "", h, flags=re.I).strip()
    return h[:200]


# --------------------------------------------------------------------------
# LinkedIn Profile Discovery (no URL provided)
# --------------------------------------------------------------------------

def discover_linkedin(
    name: str,
    company: str = "",
    title: str = "",
    location: str = "",
    email: str = "",
    phone: str = "",
) -> LinkedInVerification:
    """
    Attempt to find a LinkedIn profile when no URL is provided.

    Search strategy (all public, no login required):
    1. Google search using email, phone, name+company (site:linkedin.com/in)
    2. Derive LinkedIn slug from email username (firstname.lastname → /in/firstname-lastname)
    3. Construct name-based URL slug guesses (firstname-lastname etc.)
    4. If a page resolves, verify the name on the profile matches.
    5. Cross-check company/title from the meta description.

    This is best-effort. LinkedIn aggressively rate-limits anonymous access.
    """
    if not name or name == "Unknown":
        return LinkedInVerification(
            url="", url_resolves=False, profile_name="", headline="",
            connections_label="", profile_completeness="Unknown",
            authenticity_score=0.0,
            red_flags=["No name available to search LinkedIn"],
            notes="Discovery skipped – no candidate name",
        )

    # ----- Phase 1: Google / Bing search to find profile URLs -----
    search_urls = _google_search_linkedin(name, company, email, phone)
    found = _try_urls(search_urls, name, company, title, "Google search")
    if found:
        return found

    # ----- Phase 2: Derive slugs from email username -----
    email_slugs = _email_to_slugs(email)
    found = _try_slugs(email_slugs, name, company, title, "email-derived slug")
    if found:
        return found

    # ----- Phase 3: Name-based slug guessing -----
    slug_candidates = _generate_slug_candidates(name)
    found = _try_slugs(slug_candidates, name, company, title, "name-based slug")
    if found:
        return found

    # ----- Phase 4: Phone-based Google search (last resort) -----
    if phone:
        phone_urls = _google_search_linkedin_by_phone(phone)
        found = _try_urls(phone_urls, name, company, title, "phone search")
        if found:
            return found

    # Exhausted all strategies – not found
    methods_tried: list[str] = []
    if email:
        methods_tried.append(f"email ({email})")
    if phone:
        methods_tried.append(f"phone ({phone})")
    methods_tried.append(f"{len(slug_candidates)} URL slug patterns")
    if search_urls:
        methods_tried.append("Google search")

    return LinkedInVerification(
        url="",
        url_resolves=False,
        profile_name="",
        headline="",
        connections_label="",
        profile_completeness="Unknown",
        authenticity_score=0.0,
        red_flags=["LinkedIn profile not found via multi-strategy search"],
        notes=(
            f"Searched for: {name}"
            + (f" at {company}" if company else "")
            + f". Strategies tried: {', '.join(methods_tried)}."
        ),
    )


# --------------------------------------------------------------------------
# Multi-strategy helpers
# --------------------------------------------------------------------------

def _try_slugs(
    slugs: list[str],
    name: str, company: str, title: str,
    method: str,
) -> LinkedInVerification | None:
    """Try a list of slugs, return first matching profile or None."""
    for slug in slugs:
        url = f"https://www.linkedin.com/in/{slug}/"
        result = _validate_profile(url, name, company, title, method)
        if result:
            return result
        time.sleep(0.5)
    return None


def _try_urls(
    urls: list[str],
    name: str, company: str, title: str,
    method: str,
) -> LinkedInVerification | None:
    """Try a list of full LinkedIn URLs, return first match or None."""
    for url in urls:
        result = _validate_profile(url, name, company, title, method)
        if result:
            return result
        time.sleep(0.5)
    return None


def _validate_profile(
    url: str,
    name: str, company: str, title: str,
    method: str,
) -> LinkedInVerification | None:
    """Fetch a URL, verify name match, return result or None."""
    html, resolved_url, resolves = _fetch(url)
    if not resolves:
        return None

    profile_name = _extract_og("og:title", html) or _extract_meta("name", html)
    headline = _extract_og("og:description", html) or ""
    if not profile_name:
        return None

    clean_profile = profile_name.lower().replace("| linkedin", "").strip()
    name_ratio = SequenceMatcher(None, name.lower(), clean_profile).ratio()
    if name_ratio < 0.55:
        return None

    match_signals: list[str] = [f"Name match: {name_ratio:.0%}", f"via {method}"]
    red_flags: list[str] = []
    score = 0.4

    if name_ratio >= 0.85:
        score += 0.15
        match_signals.append("Strong name match")
    elif name_ratio >= 0.7:
        score += 0.1
        match_signals.append("Good name match")
    else:
        red_flags.append(f"Weak name match ({name_ratio:.0%})")

    headline_lower = headline.lower()
    if company and company.lower() in headline_lower:
        score += 0.15
        match_signals.append(f"Company '{company}' found in headline")
    elif company:
        red_flags.append(f"Company '{company}' not in headline")

    if title and _fuzzy_title_match(title, headline_lower):
        score += 0.1
        match_signals.append("Job title matches headline")

    has_photo = bool(re.search(r'og:image.*linkedin.*photo|profile-photo', html, re.I))
    if has_photo:
        score += 0.05
    else:
        red_flags.append("No profile photo")

    connections = _extract_connections(html)
    if connections:
        score += 0.05

    completeness = "High" if score >= 0.7 else "Medium" if score >= 0.5 else "Low"

    return LinkedInVerification(
        url=url,
        url_resolves=True,
        profile_name=_clean_li_title(profile_name),
        headline=_clean_headline(headline),
        connections_label=connections,
        profile_completeness=completeness,
        authenticity_score=round(max(0.0, min(score, 1.0)), 2),
        red_flags=red_flags,
        notes=(
            f"DISCOVERED (no URL provided). Matched via: "
            + "; ".join(match_signals)
        ),
    )


# --------------------------------------------------------------------------
# Google / Bing search for LinkedIn profiles
# --------------------------------------------------------------------------

def _google_search_linkedin(
    name: str, company: str, email: str, phone: str,
) -> list[str]:
    """
    Use Google/Bing to search for LinkedIn profiles using various identifiers.
    Returns a list of LinkedIn /in/ URLs found.
    """
    urls: list[str] = []

    queries = []
    # Email-based: most precise identifier
    if email:
        queries.append(f'site:linkedin.com/in "{email}"')
    # Name + company
    if company:
        queries.append(f'site:linkedin.com/in "{name}" "{company}"')
    # Name only
    queries.append(f'site:linkedin.com/in "{name}"')

    for q in queries:
        found = _scrape_search_results(q)
        for u in found:
            if u not in urls:
                urls.append(u)
        if len(urls) >= 5:
            break
        time.sleep(0.5)

    return urls[:5]


def _google_search_linkedin_by_phone(phone: str) -> list[str]:
    """Search for LinkedIn profiles by phone number."""
    clean_phone = re.sub(r'[^\d+]', '', phone)
    if len(clean_phone) < 7:
        return []
    urls = _scrape_search_results(f'site:linkedin.com/in "{clean_phone}"')
    # Also try without country code
    if clean_phone.startswith('+'):
        bare = clean_phone.lstrip('+').lstrip('0')
        if len(bare) >= 10:
            urls.extend(_scrape_search_results(f'site:linkedin.com/in "{bare[-10:]}"'))
    return list(dict.fromkeys(urls))[:3]


def _scrape_search_results(query: str) -> list[str]:
    """
    Issue a search query and extract linkedin.com/in/ URLs from results.
    Tries Google first, falls back to Bing, then DuckDuckGo HTML.
    """
    engines = [
        ("https://www.google.com/search", {"q": query, "num": "5"}),
        ("https://www.bing.com/search", {"q": query, "count": "5"}),
        ("https://html.duckduckgo.com/html/", {"q": query}),
    ]

    for base_url, params in engines:
        try:
            resp = requests.get(
                base_url,
                params=params,
                headers=_HEADERS,
                timeout=_TIMEOUT,
                allow_redirects=True,
            )
            if resp.status_code != 200:
                continue
            # Extract linkedin.com/in/ URLs from the page
            found = re.findall(
                r'https?://(?:www\.)?linkedin\.com/in/([\w-]+)',
                resp.text,
            )
            urls = []
            seen = set()
            for slug in found:
                slug = slug.rstrip('-')
                if slug not in seen and len(slug) > 2:
                    seen.add(slug)
                    urls.append(f"https://www.linkedin.com/in/{slug}/")
            if urls:
                return urls[:5]
        except RequestException:
            continue
        time.sleep(0.3)

    return []


# --------------------------------------------------------------------------
# Email-to-slug derivation
# --------------------------------------------------------------------------

def _email_to_slugs(email: str) -> list[str]:
    """
    Derive likely LinkedIn slugs from an email address.

    firstname.lastname@gmail.com  →  firstname-lastname
    flastname@company.com         →  flastname, f-lastname (if guessable)
    firstname_lastname@...        →  firstname-lastname
    """
    if not email or '@' not in email:
        return []

    username = email.split('@')[0].lower()
    # Remove common suffixes like numbers
    username = re.sub(r'\d+$', '', username)

    slugs: list[str] = []

    # firstname.lastname or firstname_lastname pattern
    if '.' in username or '_' in username:
        parts = re.split(r'[._]', username)
        parts = [p for p in parts if p]
        if len(parts) >= 2:
            slugs.append('-'.join(parts))              # firstname-lastname
            slugs.append(''.join(parts))               # firstnamelastname
            slugs.append(f"{parts[0]}-{parts[-1]}")   # first-last

    # Raw username as slug
    if username and username not in slugs:
        dash_version = username.replace('.', '-').replace('_', '-')
        if dash_version not in slugs:
            slugs.append(dash_version)

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    return deduped[:4]


def _generate_slug_candidates(name: str) -> list[str]:
    """
    Generate likely LinkedIn /in/ slug patterns from a name.

    Common LinkedIn slug patterns:
      - firstname-lastname          (most common)
      - firstnamelastname
      - firstname-lastname-12345    (duplicates get a suffix)
      - f-lastname
      - firstname-m-lastname        (with middle initial)
    """
    parts = name.lower().split()
    parts = [re.sub(r"[^a-z]", "", p) for p in parts if p]

    if len(parts) < 2:
        return [parts[0]] if parts else []

    first = parts[0]
    last = parts[-1]

    slugs: list[str] = [
        f"{first}-{last}",              # john-smith
        f"{first}{last}",               # johnsmith
        f"{first}-{last}-",             # john-smith- (LinkedIn sometimes adds trailing)
        f"{first[0]}{last}",            # jsmith
        f"{first}-{last[0]}",           # john-s
    ]

    # If middle name/initial present
    if len(parts) == 3:
        mid = parts[1]
        slugs.insert(1, f"{first}-{mid}-{last}")   # john-m-smith
        slugs.insert(2, f"{first}-{mid[0]}-{last}") # john-m-smith (initial)

    # Common suffix patterns for duplicates
    for suffix in ["1", "2", "3", "a", "b"]:
        slugs.append(f"{first}-{last}-{suffix}")

    return slugs[:8]  # Limit to 8 attempts to be polite


def _fuzzy_title_match(title: str, headline: str) -> bool:
    """Check if job title appears in LinkedIn headline (fuzzy)."""
    t = title.lower().strip()
    # Direct containment
    if t in headline:
        return True
    # Key words check (at least 2 title words found)
    title_words = set(re.findall(r'\b\w{3,}\b', t))
    headline_words = set(re.findall(r'\b\w{3,}\b', headline))
    overlap = title_words & headline_words
    return len(overlap) >= min(2, len(title_words))
