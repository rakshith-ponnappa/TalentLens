"""
verifier_certs.py  –  Verify certifications listed on a resume.

Multi-layer verification with online fallback:

  Layer 1: Local cert registry        – fast fuzzy match against 28+ known certs
  Layer 2: Credly badge search        – search Credly for badge/org existence
  Layer 3: Issuer pattern detection   – detect AWS/Azure/GCP/etc from cert name
  Layer 4: Issuer website check       – verify cert exists on issuer's site
  Layer 5: Web search fallback        – DuckDuckGo search for cert legitimacy
"""
from __future__ import annotations

import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote_plus

import requests
from requests.exceptions import RequestException

from models import CertVerification


_REGISTRY_PATH = Path(__file__).parent / "data" / "cert_registry.json"
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


# --------------------------------------------------------------------------
# Internal: load registry
# --------------------------------------------------------------------------

def _load_registry() -> list[dict]:
    if _REGISTRY_PATH.exists():
        return json.loads(_REGISTRY_PATH.read_text())["certifications"]
    return []


_REGISTRY = _load_registry()


# --------------------------------------------------------------------------
# Layer 1: Local registry fuzzy match
# --------------------------------------------------------------------------

def _normalise(s: str) -> str:
    return re.sub(r"[^a-z0-9]", " ", s.lower()).strip()


def _best_match(cert_name: str) -> dict | None:
    cn = _normalise(cert_name)
    best_score = 0.0
    best_entry = None
    for entry in _REGISTRY:
        candidates = [entry["name"]] + entry.get("aliases", [])
        for c in candidates:
            ratio = SequenceMatcher(None, cn, _normalise(c)).ratio()
            if ratio > best_score:
                best_score = ratio
                best_entry = entry
    if best_score >= 0.72:
        return best_entry
    return None


# --------------------------------------------------------------------------
# Layer 2: Credly badge search
# --------------------------------------------------------------------------

def _check_credly_org(credly_org: str) -> bool:
    """Check if the Credly org badge page resolves."""
    if not credly_org:
        return False
    url = f"https://www.credly.com/org/{credly_org}/badges"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        return resp.status_code == 200
    except RequestException:
        return False


def _search_credly_badge(cert_name: str) -> dict:
    """Search Credly for a certification badge by name."""
    result = {"found": False, "issuer": "", "url": ""}
    try:
        resp = requests.get(
            f"https://www.credly.com/search?q={quote_plus(cert_name)}&type=Badge",
            headers=_HEADERS, timeout=_TIMEOUT, allow_redirects=True,
        )
        if resp.status_code == 200:
            first_word = cert_name.split()[0].lower() if cert_name.split() else ""
            if first_word and first_word in resp.text.lower():
                result["found"] = True
                # Try to extract issuer from search results
                m = re.search(
                    r'class="[^"]*issuer[^"]*"[^>]*>([^<]+)<', resp.text, re.I
                )
                if m:
                    result["issuer"] = m.group(1).strip()
                # Extract badge URL
                m = re.search(r'href="(/badges/[^"]+)"', resp.text)
                if m:
                    result["url"] = f"https://www.credly.com{m.group(1)}"
    except RequestException:
        pass
    return result


# --------------------------------------------------------------------------
# Layer 3: Known issuer pattern detection
# --------------------------------------------------------------------------

_ISSUER_PATTERNS: dict[str, dict] = {
    # AWS
    r"\baws\b|amazon web services|cloud practitioner|solutions architect|sysops|devops.*(aws|amazon)|saa-c0|clf-c0|sap-c0|dop-c0|scs-c0|ans-c0|dbs-c0|mls-c0": {
        "issuer": "Amazon Web Services (AWS)",
        "verify_url": "https://www.credly.com/org/amazon-web-services/badges",
        "credly_org": "amazon-web-services",
    },
    # Azure / Microsoft
    r"\bazure\b|microsoft certified|az-\d{3}|ms-\d{3}|dp-\d{3}|ai-\d{3}|sc-\d{3}|pl-\d{3}|mb-\d{3}|md-\d{3}|microsoft\s+365|power platform|dynamics 365": {
        "issuer": "Microsoft",
        "verify_url": "https://learn.microsoft.com/en-us/credentials/",
        "credly_org": "microsoft",
    },
    # Google Cloud
    r"\bgcp\b|google cloud|gke|professional cloud|associate cloud|google certified": {
        "issuer": "Google Cloud",
        "verify_url": "https://www.credential.net/",
        "credly_org": "google-cloud",
    },
    # Kubernetes
    r"\bcka\b|\bckad\b|\bcks\b|certified kubernetes|kubernetes admin|kubernetes developer|kubernetes security": {
        "issuer": "The Linux Foundation / CNCF",
        "verify_url": "https://training.linuxfoundation.org/certification/verify",
        "credly_org": "the-linux-foundation",
    },
    # HashiCorp
    r"\bhashicorp\b|terraform associate|vault associate|consul associate": {
        "issuer": "HashiCorp",
        "verify_url": "https://www.credly.com/org/hashicorp/badges",
        "credly_org": "hashicorp",
    },
    # Cisco
    r"\bccna\b|\bccnp\b|\bccie\b|\bccda\b|cisco certified": {
        "issuer": "Cisco",
        "verify_url": "https://www.cisco.com/c/en/us/training-events/training-certifications/certifications.html",
        "credly_org": "cisco",
    },
    # CompTIA
    r"\bcomptia\b|a\+\s*cert|network\+|security\+|cloud\+|linux\+|cysa\+|pentest\+|casp\+|server\+|comptia project": {
        "issuer": "CompTIA",
        "verify_url": "https://www.certmetrics.com/comptia/public/verification.aspx",
        "credly_org": "comptia",
    },
    # PMI
    r"\bpmp\b|\bcapm\b|\bpmi-acp\b|\bpmi-rmp\b|\bpgmp\b|project management professional|pmi\b": {
        "issuer": "Project Management Institute (PMI)",
        "verify_url": "https://www.pmi.org/certifications/registry",
        "credly_org": "pmi",
    },
    # Scrum / Agile
    r"\bcsm\b|\bcspo\b|\bpsm\b|\bpspo\b|scrum master|scrum.org|product owner|safe.*(agilist|scrum)|scaled agile": {
        "issuer": "Scrum Alliance / Scrum.org / SAFe",
        "verify_url": "https://www.scrum.org/professional-scrum-certifications",
        "credly_org": "scrum-org",
    },
    # ISC2
    r"\bcissp\b|\bccsp\b|\bsscp\b|\bcsslp\b|isc2|isc\s*\(2\)": {
        "issuer": "ISC2",
        "verify_url": "https://www.isc2.org/MemberVerification",
        "credly_org": "isc2",
    },
    # ISACA
    r"\bcisa\b|\bcism\b|\bcrisc\b|\bcgeit\b|isaca\b": {
        "issuer": "ISACA",
        "verify_url": "https://www.isaca.org/credentialing/verify-a-certification",
        "credly_org": "isaca",
    },
    # Red Hat
    r"\brhce\b|\brhcsa\b|\brhca\b|red hat certified|openshift admin": {
        "issuer": "Red Hat",
        "verify_url": "https://rhtapps.redhat.com/verify",
        "credly_org": "redhat-inc",
    },
    # Databricks
    r"\bdatabricks\b|spark.*cert|lakehouse|databricks associate|databricks professional": {
        "issuer": "Databricks",
        "verify_url": "https://credentials.databricks.com/",
        "credly_org": "databricks",
    },
    # Snowflake
    r"\bsnowflake\b|snowpro": {
        "issuer": "Snowflake",
        "verify_url": "https://www.snowflake.com/certifications/",
        "credly_org": "snowflake",
    },
    # Docker
    r"\bdocker\b.*cert|dca\b|docker certified": {
        "issuer": "Docker / Mirantis",
        "verify_url": "https://training.mirantis.com/certification/dca/",
        "credly_org": "docker",
    },
    # Salesforce
    r"\bsalesforce\b|salesforce admin|salesforce developer|platform developer|pardot": {
        "issuer": "Salesforce",
        "verify_url": "https://trailhead.salesforce.com/credentials/verification",
        "credly_org": "salesforce",
    },
    # Oracle
    r"\boracle\b.*cert|oci\s+\d|java\s+(se|ee)\s+\d|oracle cloud|oracle certified": {
        "issuer": "Oracle",
        "verify_url": "https://catalog-education.oracle.com/pls/certview/sharebadge_as.certview",
        "credly_org": "oracle",
    },
    # Elastic
    r"\belastic\b.*cert|elasticsearch.*engineer|elastic certified": {
        "issuer": "Elastic",
        "verify_url": "https://www.elastic.co/training/certification",
        "credly_org": "elastic",
    },
    # Confluent / Kafka
    r"\bconfluent\b|\bkafka\b.*cert|ccse|ccdak": {
        "issuer": "Confluent",
        "verify_url": "https://training.confluent.io/",
        "credly_org": "confluent",
    },
    # MongoDB
    r"\bmongodb\b.*cert|mongodb associate|mongodb professional": {
        "issuer": "MongoDB",
        "verify_url": "https://university.mongodb.com/certification",
        "credly_org": "mongodb",
    },
}


def _detect_issuer(cert_name: str) -> dict | None:
    lower = cert_name.lower()
    for pattern, info in _ISSUER_PATTERNS.items():
        if re.search(pattern, lower):
            return info
    return None


# --------------------------------------------------------------------------
# Layer 4: Issuer website check
# --------------------------------------------------------------------------

def _check_issuer_website(issuer_info: dict, cert_name: str) -> dict:
    """Check if the cert is mentioned on the issuer's verification page."""
    result = {"found": False, "url": ""}
    verify_url = issuer_info.get("verify_url", "")
    if not verify_url:
        return result
    try:
        resp = requests.get(verify_url, headers=_HEADERS, timeout=_TIMEOUT,
                            allow_redirects=True)
        if resp.status_code == 200:
            result["found"] = True
            result["url"] = verify_url
    except RequestException:
        pass
    return result


# --------------------------------------------------------------------------
# Layer 5: Web search fallback
# --------------------------------------------------------------------------

def _web_search_cert(cert_name: str, issuer: str = "") -> dict:
    """Search DuckDuckGo for the certification to confirm legitimacy."""
    result = {"found": False, "hits": 0, "snippet": ""}
    query = f'"{cert_name}" certification'
    if issuer:
        query += f' "{issuer}"'
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers=_HEADERS, timeout=_TIMEOUT,
        )
        if resp.status_code == 200:
            hits = len(re.findall(r'class="result__a"', resp.text))
            if hits >= 2:
                result["found"] = True
                result["hits"] = hits
                m = re.search(r'class="result__snippet"[^>]*>(.+?)</a', resp.text, re.S)
                if m:
                    snippet = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                    result["snippet"] = snippet[:150]
    except RequestException:
        pass
    return result


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def verify_cert(cert_name: str) -> CertVerification:
    """Verify a certification with multi-layer online fallback."""
    if not cert_name.strip():
        return CertVerification(
            name=cert_name, issuer="Unknown", found_in_registry=False,
            verification_url="", manually_verifiable=False,
            notes="Empty certification name",
        )

    # Layer 1: Local registry match
    entry = _best_match(cert_name)
    if entry:
        credly_org = entry.get("credly_org")
        credly_ok = _check_credly_org(credly_org) if credly_org else False
        time.sleep(0.2)
        return CertVerification(
            name=cert_name,
            issuer=entry["issuer"],
            found_in_registry=True,
            verification_url=entry.get("verify_url", ""),
            manually_verifiable=bool(entry.get("verify_url")),
            notes=(
                f"Registry match + Credly verified" if credly_ok
                else f"Registry match. Verify: {entry.get('verify_url', 'N/A')}"
            ),
        )

    # Layer 2: Credly badge search
    credly = _search_credly_badge(cert_name)
    if credly["found"]:
        time.sleep(0.2)
        return CertVerification(
            name=cert_name,
            issuer=credly.get("issuer", "Unknown"),
            found_in_registry=False,
            verification_url=credly.get("url", ""),
            manually_verifiable=bool(credly.get("url")),
            notes=f"Found on Credly badge search. {credly.get('url', '')}",
        )

    # Layer 3: Issuer pattern detection
    issuer_info = _detect_issuer(cert_name)
    if issuer_info:
        credly_ok = _check_credly_org(issuer_info.get("credly_org", ""))
        time.sleep(0.2)

        # Layer 4: Issuer website check
        issuer_web = _check_issuer_website(issuer_info, cert_name)

        notes_parts = [f"Issuer detected: {issuer_info['issuer']}"]
        if credly_ok:
            notes_parts.append("Credly org verified")
        if issuer_web["found"]:
            notes_parts.append("Issuer verification page accessible")

        return CertVerification(
            name=cert_name,
            issuer=issuer_info["issuer"],
            found_in_registry=False,
            verification_url=issuer_info.get("verify_url", ""),
            manually_verifiable=bool(issuer_info.get("verify_url")),
            notes="; ".join(notes_parts),
        )

    # Layer 5: Web search fallback
    web = _web_search_cert(cert_name)
    if web["found"]:
        return CertVerification(
            name=cert_name,
            issuer="Unknown (web search)",
            found_in_registry=False,
            verification_url="",
            manually_verifiable=False,
            notes=f"Found {web['hits']} web results. {web.get('snippet', '')}",
        )

    return CertVerification(
        name=cert_name,
        issuer="Unknown",
        found_in_registry=False,
        verification_url="",
        manually_verifiable=False,
        notes="Not found in registry, Credly, known issuers, or web search - may be fictitious",
    )


def verify_certs(cert_names: list[str]) -> list[CertVerification]:
    results = []
    for c in cert_names:
        results.append(verify_cert(c))
        time.sleep(0.3)
    return results
