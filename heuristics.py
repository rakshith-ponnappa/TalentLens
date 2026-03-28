"""
heuristics.py  –  Rule-based extraction utilities (zero LLM required).

Automatically used when no API key is configured.
Shared between jd_analyzer.py and resume_parser.py.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from models import EducationEntry, ExperienceEntry


# ---------------------------------------------------------------------------
# Skills Taxonomy  –  (canonical_name, [search_aliases])
# ---------------------------------------------------------------------------
_SKILL_ENTRIES: list[tuple[str, list[str]]] = [
    # Cloud Platforms
    ("aws",                         ["amazon web services"]),
    ("azure",                       ["microsoft azure"]),
    ("gcp",                         ["google cloud platform", "google cloud"]),
    # AWS Core
    ("ec2",                         ["amazon ec2"]),
    ("s3",                          ["amazon s3"]),
    ("rds",                         ["amazon rds"]),
    ("aws lambda",                  ["lambda function", "lambda functions"]),
    ("cloudformation",              ["aws cloudformation"]),
    ("eks",                         ["elastic kubernetes service", "amazon eks"]),
    ("ecs",                         ["elastic container service", "aws fargate", "fargate"]),
    ("vpc",                         ["virtual private cloud", "amazon vpc"]),
    ("iam",                         ["aws iam", "identity and access management"]),
    ("cloudwatch",                  ["amazon cloudwatch"]),
    ("route 53",                    ["route53"]),
    ("sns",                         ["simple notification service"]),
    ("sqs",                         ["simple queue service"]),
    ("dynamodb",                    ["amazon dynamodb"]),
    ("aurora",                      ["amazon aurora"]),
    ("aws glue",                    ["glue etl"]),
    ("kinesis",                     ["amazon kinesis"]),
    ("cloudtrail",                  ["aws cloudtrail"]),
    ("secrets manager",             ["aws secrets manager"]),
    ("direct connect",              ["aws direct connect"]),
    ("transit gateway",             ["aws transit gateway"]),
    ("aws control tower",           ["control tower"]),
    ("aws organizations",           ["multi-account strategy"]),
    # AWS Migration
    ("aws migration hub",           ["migration hub"]),
    ("aws dms",                     ["database migration service", "aws database migration"]),
    ("aws mgn",                     ["application migration service", "cloudendure", "cloud endure"]),
    ("aws sct",                     ["schema conversion tool"]),
    ("aws map",                     ["migration acceleration program", "map program"]),
    ("application discovery service", ["aws ads"]),
    ("well-architected framework",  ["aws well-architected", "well architected review"]),
    ("cloud adoption framework",    ["aws caf", "azure caf"]),
    ("6rs",                         ["7rs", "lift and shift", "re-platform", "re-architecture", "replatform", "rearchitect"]),
    ("tco analysis",                ["total cost of ownership", "tco"]),
    # Azure
    ("azure devops",                ["ado"]),
    ("azure functions",             []),
    ("aks",                         ["azure kubernetes service"]),
    ("arm templates",               ["azure resource manager templates"]),
    ("bicep",                       []),
    ("azure monitor",               []),
    ("azure ad",                    ["azure active directory", "entra id", "microsoft entra"]),
    ("cosmos db",                   ["azure cosmos db", "cosmosdb"]),
    ("log analytics",               ["azure log analytics", "law"]),
    ("microsoft sentinel",          ["azure sentinel"]),
    ("azure firewall",              []),
    ("azure application gateway",   ["application gateway"]),
    # GCP
    ("bigquery",                    ["google bigquery"]),
    ("cloud run",                   ["google cloud run"]),
    ("pubsub",                      ["pub/sub", "google pub sub"]),
    ("gke",                         ["google kubernetes engine"]),
    ("cloud functions",             ["google cloud functions"]),
    ("cloud storage",               ["google cloud storage", "gcs bucket"]),
    ("cloud sql",                   ["google cloud sql"]),
    ("compute engine",              ["google compute engine"]),
    ("app engine",                  ["google app engine"]),
    # Container / Orchestration
    ("kubernetes",                  ["k8s"]),
    ("helm",                        ["helm charts"]),
    ("docker",                      ["dockerfile", "containerization", "docker compose", "docker swarm", "docker buildx"]),
    ("podman",                      []),
    ("openshift",                   ["red hat openshift"]),
    ("rancher",                     []),
    # IaC
    ("terraform",                   ["opentofu", "hcl"]),
    ("ansible",                     []),
    ("pulumi",                      []),
    ("packer",                      []),
    ("chef",                        []),
    ("puppet",                      []),
    # CI/CD
    ("jenkins",                     []),
    ("github actions",              ["github workflows"]),
    ("azure pipelines",             ["azure devops pipelines"]),
    ("gitlab ci",                   ["gitlab pipelines", "gitlab cicd"]),
    ("circleci",                    []),
    ("argocd",                      ["argo cd"]),
    ("fluxcd",                      ["flux cd"]),
    ("tekton",                      []),
    ("spinnaker",                   []),
    ("codefresh",                   ["code fresh"]),
    ("bamboo",                      ["atlassian bamboo"]),
    # Languages
    ("python",                      []),
    ("java",                        []),
    ("golang",                      ["go language", "go programming"]),
    ("javascript",                  ["node.js", "nodejs"]),
    ("typescript",                  []),
    ("c#",                          [".net framework", "dotnet", "asp.net"]),
    ("bash",                        ["shell scripting", "shell script", "bash scripting"]),
    ("powershell",                  []),
    ("ruby",                        []),
    ("rust",                        []),
    ("scala",                       []),
    ("kotlin",                      []),
    ("groovy",                      []),
    # Databases
    ("postgresql",                  ["postgres"]),
    ("mysql",                       []),
    ("mongodb",                     ["mongo"]),
    ("redis",                       []),
    ("elasticsearch",               ["opensearch"]),
    ("sql server",                  ["mssql", "microsoft sql server"]),
    ("oracle database",             ["oracle db", "oracle rdbms"]),
    ("cassandra",                   ["apache cassandra"]),
    # Monitoring / Observability
    ("datadog",                     []),
    ("prometheus",                  []),
    ("grafana",                     []),
    ("splunk",                      []),
    ("new relic",                   ["newrelic"]),
    ("pagerduty",                   []),
    ("opentelemetry",               ["otel"]),
    ("dynatrace",                   []),
    # Networking
    ("networking",                  ["network engineering", "network architecture"]),
    ("load balancing",              ["load balancer"]),
    ("nginx",                       []),
    ("istio",                       []),
    ("service mesh",                []),
    ("dns",                         []),
    ("vpn",                         []),
    # Security
    ("devsecops",                   ["dev sec ops"]),
    ("hashicorp vault",             ["vault secrets"]),
    ("zero trust",                  ["zero-trust"]),
    ("siem",                        []),
    ("owasp",                       []),
    # Methodologies
    ("agile",                       ["scrum", "kanban"]),
    ("devops",                      []),
    ("sre",                         ["site reliability engineering"]),
    ("microservices",               ["micro services"]),
    ("rest api",                    ["restful api", "rest apis"]),
    ("ci/cd",                       ["cicd", "continuous integration", "continuous deployment", "continuous delivery"]),
    ("gitops",                      ["git ops"]),
    ("infrastructure as code",      ["iac"]),
    ("platform engineering",        []),
    ("cloud native",                ["cloud-native"]),
    # OS / Infra
    ("linux",                       ["ubuntu", "rhel", "centos", "amazon linux", "red hat enterprise", "debian"]),
    ("windows server",              []),
    ("vmware",                      ["vsphere", "vcenter", "esxi"]),
    ("hybrid cloud",                []),
    ("multi-cloud",                 ["multicloud"]),
    # Data
    ("apache spark",                ["pyspark"]),
    ("apache kafka",                ["kafka"]),
    ("apache airflow",              ["airflow"]),
    ("snowflake",                   []),
    ("databricks",                  []),
    ("dbt",                         ["data build tool"]),
    # Version Control
    ("git",                         ["github", "gitlab", "bitbucket", "version control"]),
    # Other tools
    ("jira",                        ["atlassian jira"]),
    ("confluence",                  []),
    ("servicenow",                  []),
    ("sonarqube",                   []),
    ("artifactory",                 ["jfrog artifactory"]),
    ("nexus",                       ["sonatype nexus"]),
    # Compliance / Process
    ("itil",                        ["itil process", "itil framework"]),
    ("pci dss",                     ["pci compliance"]),
    ("nist",                        ["nist framework", "nist compliance"]),
    ("soc 2",                       ["soc2"]),
    # AWS extras
    ("aws ssm",                     ["systems manager", "aws systems manager"]),
    ("trusted advisor",             ["aws trusted advisor"]),
    ("compute optimizer",           ["aws compute optimizer"]),
    ("landing zone",                ["aws landing zone"]),
    ("scp",                         ["service control policies"]),
    ("config",                      ["aws config"]),
    ("guardduty",                   ["amazon guardduty"]),
    ("cost explorer",               ["aws cost explorer"]),
    ("aws budgets",                 []),
]


def extract_skills(text: str) -> set[str]:
    """Scan text for known skill terms; return set of canonical names."""
    lower = text.lower()
    found: set[str] = set()
    for canonical, aliases in _SKILL_ENTRIES:
        terms = [canonical] + aliases
        for term in terms:
            t = term.lower()
            if len(t) <= 3:
                # Short terms: require non-alphanumeric boundary to avoid false matches
                if re.search(r'(?<![a-z0-9])' + re.escape(t) + r'(?![a-z0-9])', lower):
                    found.add(canonical)
                    break
            else:
                if t in lower:
                    found.add(canonical)
                    break
    return found


# ---------------------------------------------------------------------------
# Certification extraction
# ---------------------------------------------------------------------------

def _load_cert_names() -> list[tuple[str, list[str]]]:
    reg = Path(__file__).parent / "data" / "cert_registry.json"
    if not reg.exists():
        return []
    data = json.loads(reg.read_text())
    return [(e["name"], e.get("aliases", [])) for e in data.get("certifications", [])]


_CERT_ENTRIES = _load_cert_names()


def _norm_dashes(s: str) -> str:
    """Normalize em-dash, en-dash, and double-dash to a plain hyphen."""
    return re.sub(r'[\u2013\u2014]|--', '-', s)


def extract_certs(text: str) -> list[str]:
    """Return cert names found in text, matched against the registry."""
    lower = _norm_dashes(text.lower())
    found = []
    for name, aliases in _CERT_ENTRIES:
        for term in [name] + aliases:
            if _norm_dashes(term.lower()) in lower:
                found.append(name)
                break
    return found


# ---------------------------------------------------------------------------
# JD helpers
# ---------------------------------------------------------------------------

_EXP_PATTERNS = [
    re.compile(r'(\d+)\s*(?:to|-)\s*(\d+)\s*years?', re.I),
    re.compile(r'(\d+)\+\s*years?', re.I),
    re.compile(r'minimum\s+(?:of\s+)?(\d+)\s*years?', re.I),
    re.compile(r'at\s+least\s+(\d+)\s*years?', re.I),
    re.compile(r'(\d+)\s*years?\s+(?:of\s+)?experience', re.I),
    re.compile(r'experience\s+(?:of\s+)?(\d+)\s*years?', re.I),
]


def extract_experience_range(text: str) -> tuple[float, float]:
    """Return (min_years, max_years). max=0 means no upper bound stated."""
    m = re.search(r'(\d+)\s*(?:to|-)\s*(\d+)\s*years?', text, re.I)
    if m:
        return float(m.group(1)), float(m.group(2))
    for pat in _EXP_PATTERNS:
        m = pat.search(text)
        if m:
            return float(m.group(1)), 0.0
    return 0.0, 0.0


_EDU_PATTERNS = [
    (re.compile(r'\b(?:ph\.?d\.?|doctorate|doctor\s+of\s+philosophy)\b', re.I), "PhD"),
    (re.compile(r"\b(?:master'?s?|m\.?s\.?|m\.?eng\.?|mba|m\.?sc\.?|m\.?e\.?\b)\b", re.I), "Master"),
    (re.compile(r"\b(?:bachelor'?s?|b\.?s\.?|b\.?eng\.?|b\.?tech\.?|b\.?sc\.?|b\.?e\.?\b|undergraduate)\b", re.I), "Bachelor"),
]


def extract_education_level(text: str) -> str:
    for pat, level in _EDU_PATTERNS:
        if pat.search(text):
            return level
    return "Any"


def extract_role_level(text: str, title: str = "") -> str:
    combined = (title + " " + text[:600]).lower()
    if any(w in combined for w in ["principal engineer", "distinguished", "staff engineer", "fellow"]):
        return "Principal"
    if any(w in combined for w in ["lead ", "tech lead", "team lead", "engineering lead", "technical lead"]):
        return "Lead"
    if any(w in combined for w in ["senior", "sr.", " sr "]):
        return "Senior"
    if any(w in combined for w in ["junior", "jr.", " jr ", "associate engineer", "entry-level", "entry level"]):
        return "Junior"
    if any(w in combined for w in ["manager", "director", "vice president", " vp ", "head of", "cto", "cio"]):
        return "Executive"
    min_exp, _ = extract_experience_range(text)
    if min_exp >= 8:
        return "Senior"
    if min_exp >= 4:
        return "Mid"
    if min_exp >= 1:
        return "Junior"
    return "Mid"


_REQ_HDR = re.compile(
    r'^.{0,15}(?:required|must.have|qualifications?|requirements?|what you.?ll need|'
    r'minimum qualifications?|basic qualifications?|you have|you bring|you will have).{0,15}$',
    re.I | re.M,
)
_PREF_HDR = re.compile(
    r'^.{0,15}(?:preferred|nice.to.have|bonus|desired|additional qualifications?|'
    r'what would be.+nice|plus.{0,15}).{0,15}$',
    re.I | re.M,
)


def split_jd_sections(text: str) -> tuple[str, str]:
    """Return (required_text, preferred_text). Falls back to (full_text, '') if no sections found."""
    req_m = _REQ_HDR.search(text)
    pref_m = _PREF_HDR.search(text)

    if not req_m and not pref_m:
        return text, ""

    if req_m and pref_m:
        r_start, p_start = req_m.end(), pref_m.end()
        if r_start < p_start:
            return text[r_start:pref_m.start()], text[p_start:]
        return text[r_start:], text[p_start:req_m.start()]

    if req_m:
        return text[req_m.end():], ""
    return text, text[pref_m.end():]


_TITLE_SKIP = re.compile(
    r'(?:job\s+(?:description|posting|id)|position\s+overview|about\s+(?:the|us|our)|'
    r'we\s+are\s+(?:looking|seeking|hiring)|company|department|location\s*:|type\s*:|'
    r'salary|compensation|overview|requisition)',
    re.I,
)


def extract_jd_title(text: str) -> str:
    """Extract job title from the first lines of the JD."""
    for line in text.split('\n')[:12]:
        line = line.strip()
        if not line or len(line) < 4 or len(line) > 100:
            continue
        if _TITLE_SKIP.search(line):
            continue
        if re.match(r'^[\d\s/\-\.\|]+$', line):
            continue
        return line
    return "Unknown Role"


_INDUSTRY_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\b(?:fintech|financial|bank|insurance|trading|payment|capital market)\b', re.I), "Financial Services"),
    (re.compile(r'\b(?:healthcare|medical|pharma|clinical|hospital|health\s+tech)\b', re.I), "Healthcare"),
    (re.compile(r'\b(?:retail|e-?commerce|consumer|marketplace)\b', re.I), "Retail / E-Commerce"),
    (re.compile(r'\b(?:manufacturing|industrial|supply\s+chain|factory)\b', re.I), "Manufacturing"),
    (re.compile(r'\b(?:media|entertainment|streaming|gaming)\b', re.I), "Media & Entertainment"),
    (re.compile(r'\b(?:government|public\s+sector|federal|defense)\b', re.I), "Government"),
    (re.compile(r'\b(?:education|university|academic|edtech)\b', re.I), "Education"),
    (re.compile(r'\b(?:consulting|professional\s+services|advisory|managed\s+services)\b', re.I), "Consulting"),
    (re.compile(r'\b(?:telecom|telecommunication|5g)\b', re.I), "Telecommunications"),
]


def infer_industry(text: str) -> str:
    for pat, industry in _INDUSTRY_MAP:
        if pat.search(text):
            return industry
    return "Technology"


# ---------------------------------------------------------------------------
# Resume contact extraction
# ---------------------------------------------------------------------------

def extract_email(text: str) -> str:
    m = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
    return m.group(0) if m else ""


def extract_phone(text: str) -> str:
    m = re.search(
        r'(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}',
        text,
    )
    return m.group(0).strip() if m else ""


def extract_linkedin_url(text: str) -> str:
    m = re.search(r'https?://(?:www\.)?linkedin\.com/in/[\w%-]+/?', text, re.I)
    if m:
        return m.group(0)
    m = re.search(r'linkedin\.com/in/([\w%-]+)', text, re.I)
    return f"https://www.linkedin.com/in/{m.group(1)}" if m else ""


def extract_github_url(text: str) -> str:
    m = re.search(r'https?://(?:www\.)?github\.com/[\w-]+/?', text, re.I)
    if m:
        return m.group(0)
    m = re.search(r'github\.com/([\w-]+)', text, re.I)
    return f"https://github.com/{m.group(1)}" if m else ""


# Words that commonly cause false-positive location matches
_NOT_LOCATION = re.compile(
    r'(?:Amazon|AWS|Azure|Google|Cloud|VPC|Elastic|Snowball|Server|'
    r'Discovery|Migration|Infrastructure|Service|Block|Storage|Lambda|'
    r'Automation|Skilled|Platform|Kubernetes|Docker|Jenkins|Terraform|'
    r'ISAM|DMS|Certified|Professional|Technology|Solutions|Limited|'
    r'SNS|SQS|IAM|Route|Balancer|Glacier|Trail|CloudWatch|Beanstalk|'
    r'Carbonite|Doubletake|Splunk|Ansible|Maven|Nexus|Grafana|'
    r'Prometheus|Sonar|Dynatrace|Datadog|Packer|Vault|Redis|Kafka)',
    re.I,
)


def extract_location(text: str) -> str:
    # First look for explicit location patterns in the header (first ~10 lines)
    header = '\n'.join(text.split('\n')[:15])

    # Pattern: "City, State" or "City, Country"
    for m in re.finditer(r'\b([A-Z][a-zA-Z\s]{2,25}),\s*([A-Z]{2}|[A-Z][a-zA-Z\s]{3,20})\b', header):
        full = m.group(0)
        if not _NOT_LOCATION.search(full):
            return full

    # Fallback: look for known Indian cities/US states in first 20 lines
    header20 = '\n'.join(text.split('\n')[:20])
    cities_re = re.compile(
        r'\b(Bangalore|Bengaluru|Chennai|Mumbai|Hyderabad|Pune|Delhi|'
        r'Kolkata|Noida|Gurgaon|Gurugram|Ahmedabad|Jaipur|Kochi|Coimbatore|'
        r'New York|San Francisco|Seattle|Austin|Chicago|Dallas|Boston|'
        r'London|Toronto|Dubai|Singapore)\b',
        re.I,
    )
    m = cities_re.search(header20)
    return m.group(0) if m else ""


_NAME_BLOCKLIST = re.compile(
    r'^\s*(?:curriculum\s+vitae|resume|biodata|bio[\s-]?data|'
    r'profile\s*summary|personal\s+(?:details|information|data|profile)|'
    r'cover\s+letter|professional\s+(?:summary|profile|experience)|'
    r'career\s+(?:objective|summary)|objective|summary|'
    r'work\s+experience|technical\s+skills|education|'
    r'contact\s+(?:details|information|info)|phone|email|address|'
    r'confidential|private|declaration|references|'
    r'page\s+\d|updated?\s+\d|date\s*:)\s*$',
    re.I,
)

_LOCATION_WORDS = re.compile(
    r'\b(?:bangalore|bengaluru|chennai|mumbai|hyderabad|pune|delhi|'
    r'kolkata|noida|gurgaon|gurugram|ahmedabad|jaipur|kochi|coimbatore|'
    r'new\s+york|san\s+francisco|seattle|austin|chicago|dallas|boston|'
    r'london|toronto|dubai|singapore|india|karnataka|kerala|maharashtra|'
    r'tamil\s+nadu|telangana|andhra\s+pradesh|uttar\s+pradesh|'
    r'kempapura|hebbal|whitefield|marathahalli|koramangala|'
    r'electronic\s+city|hsr\s+layout|btm\s+layout|indiranagar|'
    r'jayanagar|jp\s+nagar|rajajinagar|malleswaram|'
    r'street|road|lane|cross|main|nagar|layout|colony|phase|sector)\b',
    re.I,
)


def _name_from_email(email: str) -> str:
    """Try to derive a human name from an email local part."""
    if not email or '@' not in email:
        return ""
    local = email.split('@')[0]
    # Strip trailing digits
    local = re.sub(r'\d+$', '', local)
    # Split on . _ - and camelCase boundaries
    parts = re.split(r'[._\-]', local)
    if len(parts) == 1:
        # Try camelCase split
        parts = re.findall(r'[A-Z]?[a-z]+', local)
    if len(parts) < 2:
        return ""
    # Filter out short noise parts
    parts = [p for p in parts if len(p) >= 2]
    if len(parts) < 2:
        return ""
    return ' '.join(p.capitalize() for p in parts[:3])


def extract_name(lines: list[str], email: str = "") -> str:
    """Heuristic: first short all-alpha line at top of resume is the name.

    Enhanced with:
      - Blocklist for common non-name headers (CURRICULUM VITAE, etc.)
      - Location detection to skip address lines
      - Email-based name fallback
    """
    for line in lines[:8]:
        line = line.strip()
        if not line or len(line) > 60 or '@' in line:
            continue
        if re.search(r'https?://', line, re.I):
            continue
        if re.match(r'^[\d\s\-+().]+$', line):
            continue
        # Skip known non-name headers
        if _NAME_BLOCKLIST.match(line):
            continue
        # Skip lines that look like a location/address
        loc_matches = _LOCATION_WORDS.findall(line)
        words = line.split()
        if loc_matches and len(loc_matches) >= len(words) * 0.5:
            continue
        if 2 <= len(words) <= 5 and all(re.match(r"^[A-Za-z][a-zA-Z'\-\.]*$", w) for w in words):
            return line

    # Fallback: try to derive name from email address
    email_name = _name_from_email(email)
    if email_name:
        return email_name

    return "Unknown"


# ---------------------------------------------------------------------------
# Experience block parsing
# ---------------------------------------------------------------------------

_MON = (r'(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
        r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)')
_DATE_RNG = re.compile(
    rf'(?:From\s+)?({_MON}\.?\s*[\',]?\s*\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{1,2}}-\d{{4}}|\d{{4}}-\d{{2}}|\d{{4}})'
    rf'\s*(?:–|—|-|~|to)\s*'
    rf'({_MON}\.?\s*[\',]?\s*\d{{4}}|\d{{1,2}}/\d{{4}}|\d{{1,2}}-\d{{4}}|\d{{4}}-\d{{2}}|\d{{4}}|'
    rf'[Pp]resent|[Cc]urrent|[Nn]ow|[Tt]ill\s+[Dd]ate|[Oo]ngoing|[Cc]ontinuing)',
    re.I,
)

# Fallback regex for total experience mentioned in text
_TOTAL_EXP_TEXT = re.compile(
    r'(?:(?:over|around|approximately|nearly|about|~)\s+)?'
    r'(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)\s+(?:of\s+)?'
    r'(?:experience|exp|professional\s+experience|it\s+experience|work\s+experience)',
    re.I,
)
_TOTAL_EXP_TEXT2 = re.compile(
    r'(?:experience|exp)\s*(?:of\s+|:?\s*)(\d{1,2}(?:\.\d)?)\s*\+?\s*(?:years?|yrs?)',
    re.I,
)


def _parse_date_str(s: str) -> Optional[date]:
    s = s.strip().rstrip("',")
    for fmt in ['%B %Y', '%b %Y', '%b. %Y', '%m/%Y', '%m-%Y', '%Y-%m',
                '%B, %Y', '%b, %Y', '%B %d %Y', '%d %B %Y',
                '%Y']:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    m = re.search(r'\d{4}', s)
    if m:
        return date(int(m.group()), 6, 1)  # mid-year when only year given
    return None


def _guess_company_title(lines: list[str], date_str: str) -> tuple[str, str]:
    """Extract (company, title) from the experience block context lines."""
    date_idx = None
    for i, line in enumerate(lines):
        if re.search(r'\d{4}', line) and re.search(r'[–—\-]|to\b', line, re.I):
            date_idx = i
            break

    if date_idx is None:
        return "Unknown", "Unknown"

    # Look at lines BEFORE the date line for the title/company info
    # Common formats:
    #   "Title, Company, Location."  (single line, comma-separated)
    #   "Title | Company | Date"     (pipe-separated on date line)
    #   "Company\nTitle\nDate"       (separate lines)

    # Check the line immediately before the date
    if date_idx > 0:
        prev_line = lines[date_idx - 1].rstrip('.')

        # Pattern: "Title, Company Name, Location"  (3+ comma parts)
        comma_parts = [p.strip() for p in prev_line.split(',') if p.strip()]
        if len(comma_parts) >= 3:
            # First part = title, middle parts = company, last = location
            title = comma_parts[0]
            company = ', '.join(comma_parts[1:-1])
            return company.strip(), title.strip()
        if len(comma_parts) == 2:
            # Could be "Company, Location" or "Title, Company"
            # Check if second part looks like a location (city/state)
            if re.match(r'^[A-Z][a-zA-Z\s]{2,20}$', comma_parts[1].strip()):
                # "Company, Location" → check line before for title
                company = comma_parts[0]
                if date_idx > 1:
                    title = lines[date_idx - 2][:70].rstrip('.')
                else:
                    title = "Unknown"
                return company.strip(), title.strip()
            return comma_parts[1].strip(), comma_parts[0].strip()

    # Pipe/bullet separated on the same line as date?
    date_line = lines[date_idx]
    parts = re.split(r'\s*[\|•·]\s*', date_line)
    non_date = [p.strip() for p in parts if p.strip() and not re.search(r'\d{4}.*[–\-]', p)]
    if len(non_date) >= 2:
        return non_date[1], non_date[0]
    if len(non_date) == 1 and date_idx > 0:
        return non_date[0], lines[date_idx - 1][:70]

    title = lines[date_idx - 1][:70] if date_idx > 0 else "Unknown"
    company = lines[date_idx - 2][:70] if date_idx > 1 else "Unknown"
    return company, title


def extract_experience_blocks(text: str) -> list[ExperienceEntry]:
    """Parse work history date ranges and surrounding context from resume text."""
    entries: list[ExperienceEntry] = []
    today = date.today()
    seen_positions: set[int] = set()

    for m in _DATE_RNG.finditer(text):
        start_str = m.group(1)
        end_str = m.group(2)

        start_d = _parse_date_str(start_str)
        is_current = bool(re.match(r'(?:present|current|now|till\s+date|ongoing|continuing)', end_str.strip(), re.I))
        end_d = today if is_current else _parse_date_str(end_str)

        if not start_d or not end_d:
            continue
        months = (end_d.year - start_d.year) * 12 + (end_d.month - start_d.month)
        if months < 0 or months > 480:
            continue

        # Deduplicate overlapping matches
        if any(abs(m.start() - p) < 50 for p in seen_positions):
            continue
        seen_positions.add(m.start())

        ctx_start = max(0, m.start() - 250)
        ctx_end = min(len(text), m.end() + 400)
        block = text[ctx_start:ctx_end]
        lines = [ln.strip() for ln in block.split('\n') if ln.strip()]

        company, title = _guess_company_title(lines, m.group(0))

        entries.append(ExperienceEntry(
            company=company,
            title=title,
            start_date=start_str,
            end_date="Present" if is_current else end_str,
            duration_months=max(months, 0),
            location="",
            description=block[:400].strip(),
        ))

    return entries


def calc_total_years(entries: list[ExperienceEntry], raw_text: str = "") -> float:
    if entries:
        return round(sum(e.duration_months for e in entries) / 12, 1)
    # Fallback: look for total experience mentioned in text
    if raw_text:
        for pat in (_TOTAL_EXP_TEXT, _TOTAL_EXP_TEXT2):
            m = pat.search(raw_text)
            if m:
                return float(m.group(1))
    return 0.0


# ---------------------------------------------------------------------------
# Education block parsing
# ---------------------------------------------------------------------------

# Education degree patterns — anchored to avoid matching inside AWS service names
# or job titles like "Associate Consultant"
_DEG_PATTERNS = [
    (re.compile(r'\b(?:ph\.?d\.?|doctorate|doctor\s+of\s+philosophy)\b', re.I), "PhD"),
    (re.compile(
        r"(?:^|[\s,;(])(?:master'?s?\s+(?:of|in|degree)\b|mba\b|m\.?tech\.?\b|m\.?eng\.?\b|m\.?sc\.?\b"
        r"|m\.?s\.?\s+(?:in|of)\b|master\s+of\s+(?:science|business|arts|engineering))",
        re.I | re.M,
    ), "Master"),
    (re.compile(
        r"(?:^|[\s,;(])(?:b\.?tech\.?\b|b\.?eng\.?\b|b\.?e\.?\b|b\.?s\.?\s+(?:in|of)\b"
        r"|b\.?sc\.?\b|bachelor'?s?\s+(?:of|in|degree)\b"
        r"|bachelor\s+of\s+(?:science|arts|engineering|technology|computer)"
        r"|bachelors?\s+in\s+technology\b)",
        re.I | re.M,
    ), "Bachelor"),
    (re.compile(
        r"(?:^|[\s,;(])(?:associate'?s?\s+(?:degree|of)\b|diploma\s+in\b)",
        re.I | re.M,
    ), "Associate"),
]
_GRAD_YEAR = re.compile(r'\b((?:19|20)\d{2})\b')
_UNIV_KW = re.compile(
    r'\b(?:university|college|institute|school|academy|polytechnic'
    r'|engineering\s+&?\s*technology)\b', re.I
)


# Section header that signals we're in the education part of the resume
_EDU_SECTION_RE = re.compile(
    r'^\s*(?:EDUCATION|ACADEMIC\s*(?:BACKGROUND|QUALIFICATION)?'
    r'|QUALIFICATION|EDUCATIONAL\s+QUALIFICATION)S?\s*:?\s*$',
    re.I | re.M,
)


def _extract_edu_section(text: str) -> str:
    """Return just the education section of the resume, or full text as fallback."""
    m = _EDU_SECTION_RE.search(text)
    if not m:
        return text
    start = m.end()
    # Education section ends at next section header or EOF
    next_header = re.search(
        r'^\s*(?:EXPERIENCE|PROJECTS?|SKILLS?|CERTIFIC|WORK\s+HISTORY|'
        r'PROFESSIONAL|ACCOMPLISHMENT|SUMMARY|OBJECTIVE|INTEREST|HOBBIES|'
        r'PERSONAL|REFERENCE|DECLARATION)\S*\s*$',
        text[start:], re.I | re.M,
    )
    end = start + next_header.start() if next_header else len(text)
    return text[start:end]


def extract_education_blocks(text: str) -> list[EducationEntry]:
    """Parse education entries from resume text."""
    edu_text = _extract_edu_section(text)
    entries: list[EducationEntry] = []
    seen: set[str] = set()

    for pat, degree_label in _DEG_PATTERNS:
        for m in pat.finditer(edu_text):
            ctx_start = max(0, m.start() - 80)
            ctx_end = min(len(edu_text), m.end() + 250)
            block = edu_text[ctx_start:ctx_end]

            if block in seen:
                continue
            seen.add(block)

            year_m = _GRAD_YEAR.search(block)
            grad_year = int(year_m.group(1)) if year_m else None

            # Extract field of study
            after = edu_text[m.end():m.end() + 120]
            field_m = re.search(r'(?:in|of)\s+([A-Za-z][A-Za-z\s&]{2,40}?)(?:\s*\(|\n|,\s*[A-Z]|$)', after)
            field = ""
            # Reject garbage fields
            _bad_field = re.compile(
                r'(?:EXPERIENCE|PROFESSIONAL|PROJECTS?|till|date|CERTIFICATION|SUMMARY|SKILL)',
                re.I,
            )
            if field_m:
                candidate_field = field_m.group(1).strip()
                if not _UNIV_KW.search(candidate_field) and not _bad_field.search(candidate_field):
                    field = candidate_field

            # Extract institution from the same line or nearby lines
            institution = _find_institution(block, edu_text, m.start())

            entries.append(EducationEntry(
                institution=institution,
                degree=degree_label,
                field=field,
                graduation_year=grad_year,
            ))
            if len(entries) >= 4:
                return entries

    # If no patterns matched but we have an education section, try line-by-line
    if not entries and edu_text != text:
        return _fallback_edu_parse(edu_text)

    return entries


def _find_institution(block: str, full_text: str, match_pos: int) -> str:
    """Find the institution name — check same line (comma-separated), 'from X' pattern, then nearby lines."""
    for line in block.split('\n'):
        line = line.strip()
        if not line:
            continue

        # Pattern: "from XYZ University" or "from CUSAT" or "from SRTMUN"
        from_m = re.search(r'\bfrom\s+([A-Z][A-Za-z\s&.\'-]{2,60}?)(?:\s+(?:in|with|,|\()\b|\s+\d|\s*$)', line)
        if from_m:
            inst = from_m.group(1).strip().rstrip('.,')
            if len(inst) > 3:
                return inst[:70]

        # Check comma-separated parts on the same line:
        # "B.E Mechanical Engineering (2016), PGP College of Eng & Tech, Namakkal."
        parts = re.split(r',\s*', line)
        for part in parts:
            part = part.strip().rstrip('.')
            if _UNIV_KW.search(part) and 4 < len(part) < 80:
                return part[:70]
            # All-caps acronyms that look like institution codes (CUSAT, BPUT, SRTMUN...)
            if re.fullmatch(r'[A-Z]{3,10}', part):
                return part

        # Check if the whole line mentions an institution
        if _UNIV_KW.search(line) and 4 < len(line) < 80:
            return line[:70]

    return "Unknown"


def _fallback_edu_parse(edu_text: str) -> list[EducationEntry]:
    """Line-by-line fallback for education sections."""
    entries: list[EducationEntry] = []
    for line in edu_text.split('\n'):
        line = line.strip()
        if not line or len(line) < 5:
            continue
        # Look for lines with a year in them
        year_m = _GRAD_YEAR.search(line)
        if not year_m:
            continue
        if not (_UNIV_KW.search(line) or re.search(
            r"B\.?[EeSc]|B\.?Tech|M\.?[SsTe]|MBA|PhD|Bachelor|Master|Diploma|degree", line, re.I
        )):
            continue

        # Determine degree
        degree = "Unknown"
        for pat, label in _DEG_PATTERNS:
            if pat.search(line):
                degree = label
                break
        # Broader fallback for "Bachelor's degree" etc.
        if degree == "Unknown":
            if re.search(r"bachelor|b\.?tech|b\.?e\b|b\.?sc", line, re.I):
                degree = "Bachelor"
            elif re.search(r"master|m\.?tech|m\.?sc|mba", line, re.I):
                degree = "Master"

        # Find institution
        institution = "Unknown"
        # Try "from X" pattern first
        from_m = re.search(r'\bfrom\s+([A-Z][A-Za-z\s&.\'-]{2,60}?)(?:\s+(?:in|with|,|\()\b|\s+\d|\s*$)', line)
        if from_m:
            institution = from_m.group(1).strip().rstrip('.,')[:70]
        else:
            parts = re.split(r',\s*', line)
            for part in parts:
                part = part.strip().rstrip('.')
                if _UNIV_KW.search(part) and 4 < len(part) < 80:
                    institution = part[:70]
                    break
                if re.fullmatch(r'[A-Z]{3,10}', part):
                    institution = part
                    break

        # Extract field of study
        field = ""
        field_m = re.search(r'(?:in|of)\s+([A-Za-z][A-Za-z\s&]{3,40}?)(?:\s+(?:B\.|from|,|\()|$)', line, re.I)
        if field_m:
            candidate = field_m.group(1).strip()
            if not _UNIV_KW.search(candidate):
                field = candidate

        entries.append(EducationEntry(
            institution=institution,
            degree=degree,
            field=field,
            graduation_year=int(year_m.group(1)),
        ))
    return entries
