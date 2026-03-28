"""
verifier_certs.py  –  Verify certifications listed on a resume.

For each certification:
  1. Match against the local cert registry to find issuer and verification URL
  2. Check Credly public API for badge existence (no auth required)
  3. Provide manual verification URL for HR to follow up
"""
from __future__ import annotations

import json
import re
import time
from difflib import SequenceMatcher
from pathlib import Path

import requests
from requests.exceptions import RequestException

from models import CertVerification


_REGISTRY_PATH = Path(__file__).parent / "data" / "cert_registry.json"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Safari/537.36"
    )
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
# Matching
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
# Credly check
# --------------------------------------------------------------------------

def _check_credly_org(credly_org: str, cert_name: str) -> bool:
    """
    Check if the Credly org page resolves.  We can't easily look up
    a specific person's badge without their profile URL, so we just
    confirm the org/cert exists on Credly.
    """
    if not credly_org:
        return False
    url = f"https://www.credly.com/org/{credly_org}/badges"
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        return resp.status_code == 200
    except RequestException:
        return False


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def verify_cert(cert_name: str) -> CertVerification:
    entry = _best_match(cert_name)
    if not entry:
        return CertVerification(
            name=cert_name,
            issuer="Unknown",
            found_in_registry=False,
            verification_url="",
            manually_verifiable=False,
            notes="Not found in known certification registry",
        )

    credly_org = entry.get("credly_org")
    credly_ok = _check_credly_org(credly_org, cert_name) if credly_org else False
    time.sleep(0.3)

    return CertVerification(
        name=cert_name,
        issuer=entry["issuer"],
        found_in_registry=True,
        verification_url=entry.get("verify_url", ""),
        manually_verifiable=bool(entry.get("verify_url")),
        notes=(
            f"Credly org page verified" if credly_ok
            else f"Use verification URL to confirm: {entry.get('verify_url', 'N/A')}"
        ),
    )


def verify_certs(cert_names: list[str]) -> list[CertVerification]:
    return [verify_cert(c) for c in cert_names]
