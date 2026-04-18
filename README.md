<div align="center">

# 🔍 TalentLens

### *See beyond the resume.*

**Multi-agent AI screening pipeline that evaluates candidates like a real hiring panel — 11 specialist agents, skills matching, background verification, and interview prep — all in one platform.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io)
[![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=for-the-badge&logo=plotly&logoColor=white)](https://plotly.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-10b981?style=for-the-badge)](LICENSE)

[![Tests](https://img.shields.io/badge/Tests-79%20passed-brightgreen?style=flat-square&logo=pytest)](tests/)
[![Coverage](https://img.shields.io/badge/Coverage-26%25-yellow?style=flat-square&logo=codecov)](htmlcov/index.html)
[![Ruff](https://img.shields.io/badge/Linter-Ruff-d4aa00?style=flat-square&logo=ruff)](https://docs.astral.sh/ruff/)
[![Bandit](https://img.shields.io/badge/SAST-Bandit-blue?style=flat-square&logo=python)](https://bandit.readthedocs.io/)
[![Gitleaks](https://img.shields.io/badge/Secrets-Gitleaks-red?style=flat-square&logo=git)](https://gitleaks.io/)
[![taskctl](https://img.shields.io/badge/Pipeline-taskctl-orange?style=flat-square)](https://github.com/taskctl/taskctl)

[**Getting Started**](#-getting-started) · [**Features**](#-features) · [**Architecture**](#-architecture) · [**Agent Panel**](#-the-11-agent-panel) · [**Dashboard**](#-dashboard) · [**CLI**](#-cli-usage) · [**DevSecOps**](#-devsecops-pipeline)

</div>

---

## 🤔 The Problem

Screening resumes manually is slow, biased, and inconsistent. Even keyword-matching tools miss context — they can't tell if a "5-year AWS engineer" actually architected production systems or just followed tutorials.

## 💡 The Solution

**TalentLens** simulates a real hiring panel. Instead of one algorithm, **11 specialist AI agents** — from a Cloud Solutions Architect to a Security Architect to an HR Manager — independently evaluate every candidate, then debate and reach consensus. The result: a multi-dimensional score that captures what no single reviewer could.

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🤖 Multi-Agent Evaluation
11 specialist agents with distinct perspectives — architecture, security, QA, cloud, HR — each scores independently, then collaborates to reach consensus.

### 📊 Hybrid Scoring Engine
TF-IDF + Sentence-BERT + Jaccard similarity combined across 6 weighted dimensions. No single metric dominates.

### 🔍 Background Verification
Company verification via OpenCorporates, LinkedIn profile validation, email MX checks, employment timeline analysis, identity cross-referencing.

</td>
<td width="50%">

### 🎯 Zero-LLM Heuristic Mode
Full pipeline works without any API keys using regex-based parsing, rule-based scoring, and NLP heuristics. No cost, no rate limits.

### 📝 Interview Questionnaire Generator
Auto-generates targeted questions based on skill gaps and agent concerns. Export as DOCX for your interview panel.

### 📈 8-Page Dashboard
Glassmorphism UI with real-time pipeline tracking, interactive Plotly charts, candidate comparison radar charts, and full screening history.

</td>
</tr>
</table>

---

## 🏗 Architecture

```mermaid
graph LR
    A["📄 JD Input"] --> B["🔬 JD Analyzer"]
    C["📤 Resume Upload"] --> D["📋 Resume Parser"]
    B --> E["⚡ Scoring Engine"]
    D --> E
    D --> F["🔍 Verifier"]
    F --> E
    E --> G["🤖 11-Agent Panel"]
    G --> H["📊 Consensus"]
    H --> I["📝 Interview Generator"]
    E --> J["🏆 Rankings"]

    style A fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style B fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style C fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style D fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style E fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style F fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
    style G fill:#1e293b,stroke:#ef4444,color:#e2e8f0
    style H fill:#1e293b,stroke:#ef4444,color:#e2e8f0
    style I fill:#1e293b,stroke:#06b6d4,color:#e2e8f0
    style J fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
```

### Module Map

```
├── main.py                  # CLI entry point (Typer)
├── dashboard_v3.py          # Streamlit 8-page dashboard
├── agents.py                # 11 specialist agent personas + consensus engine
├── scorer.py                # TF-IDF + SBERT + Jaccard scoring
├── jd_analyzer.py           # JD → structured criteria (LLM or heuristic)
├── resume_parser.py         # PDF/DOCX → candidate profile (LLM or heuristic)
├── heuristics.py            # Zero-LLM fallback: regex + NLP parsing
├── verifier.py              # Orchestrates all verification modules
│   ├── verifier_company.py  # OpenCorporates + LinkedIn company check
│   ├── verifier_certs.py    # Cert registry + Credly verification
│   ├── verifier_linkedin.py # Profile resolution + red flag detection
│   └── verifier_identity.py # Email, timeline, name cross-reference
├── pipeline.py              # Hiring pipeline state machine (SQLite)
├── comparator.py            # Multi-candidate comparison + radar charts
├── red_flags.py             # Employment gaps, title inflation, email risk
├── jd_quality.py            # JD scoring + improvement suggestions
├── archetypes.py            # Role archetype classification
├── export_engine.py         # MD/JSON/HTML/CSV/DOCX export
├── interview_gen.py         # Questionnaire generator + DOCX export
├── history.py               # SQLite persistence (sessions, candidates, JDs)
├── models.py                # Pydantic/dataclass models
├── config.py                # .env loader + weight configuration
├── tests/                   # 79 pytest tests (7 test modules)
│   ├── conftest.py          # Shared fixtures
│   ├── test_pipeline.py     # Pipeline state machine (19 tests)
│   ├── test_red_flags.py    # Red flag detection (13 tests)
│   ├── test_comparator.py   # Candidate comparison (12 tests)
│   ├── test_history.py      # Session/JD persistence (9 tests)
│   ├── test_archetypes.py   # Role classification (9 tests)
│   ├── test_export_engine.py# Export formats (7 tests)
│   └── test_jd_quality.py   # JD quality analysis (6 tests)
├── taskctl.yaml             # Local DevSecOps pipeline orchestrator
├── .pre-commit-config.yaml  # Git hooks: ruff, bandit, mypy, gitleaks
├── .github/workflows/ci.yml # GitHub Actions CI/CD pipeline
└── data/
    ├── cert_registry.json   # 30+ certifications with verification URLs
    └── known_companies.json # Company verification reference data
```

---

## 🤖 The 11-Agent Panel

Each agent brings a **unique evaluation lens**. They score independently, then engage in multi-round discussion to reach consensus.

| Agent | Focus | Weight |
|:------|:------|:------:|
| ☁️ **Cloud Solutions Architect** | AWS architecture, design patterns, Well-Architected | **14%** |
| 🔄 **AWS Migration Engineer** | Migration strategy, 6Rs, landing zones | **12%** |
| 🔒 **Security Architect** | Security posture, compliance, threat modeling | **10%** |
| 📡 **Cloud Operations Engineer** | Day-2 ops, observability, cost optimization | **10%** |
| 👥 **HR Manager** | Culture fit, career trajectory, soft skills | **10%** |
| 🏗️ **Application Architect** | System design, scalability, microservices | **8%** |
| ⚙️ **SRE Engineer** | Reliability, incident response, SLOs | **8%** |
| 🛠️ **AWS Platform Engineer** | IaC, Terraform, containers, CI/CD | **8%** |
| 🎯 **Recruiting Engineer** | Role alignment, market positioning | **8%** |
| 📦 **Product Owner** | Delivery track record, domain expertise | **6%** |
| 🧪 **QA Architect** | Testing strategy, automation, code quality | **6%** |

> Weights are tuned for cloud/platform engineering roles. Easily customizable in `agents.py`.

---

## 📊 Scoring Dimensions

The scoring engine combines **three similarity algorithms** across **six weighted dimensions**:

```
Score = TF-IDF (40%) + Sentence-BERT (40%) + Jaccard (20%)
```

| Dimension | Default Weight | What It Measures |
|:----------|:--------------:|:-----------------|
| Required Skills | **35** | Hard skill match against JD requirements |
| Experience | **25** | Years + relevance of work history |
| Preferred Skills | **15** | Nice-to-have skills and technologies |
| Education | **10** | Degree level + field relevance |
| Certifications | **10** | Verified professional certifications |
| Semantic Match | **5** | Deep contextual similarity (SBERT embeddings) |

> Weights are configurable via `.env` or the dashboard UI sliders. Must sum to 100.

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- (Optional) OpenAI or Anthropic API key — *heuristic mode works without any keys*

### Install

```bash
git clone https://github.com/rakshith-ponnappa/TalentLens.git
cd TalentLens

python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.template .env   # edit with your API keys (optional)
```

### Launch Dashboard

```bash
streamlit run dashboard_v3.py
```

> Opens at `http://localhost:8501` — 8 pages: Welcome, JD Management, Screening, Results, Agent Panel, History, Analytics, Interview Prep.

---

## 💻 CLI Usage

```bash
# Load a job description
python main.py jd path/to/job_description.pdf

# Screen resumes
python main.py screen resume1.pdf resume2.pdf resume3.docx

# Full pipeline in one command
python main.py run --jd jd.pdf --resume r1.pdf --resume r2.pdf --detail

# Top 5 only, skip background checks
python main.py screen *.pdf --top 5 --no-verify
```

---

## 🖥 Dashboard

The Streamlit dashboard provides a complete screening workflow:

| Page | Purpose |
|:-----|:--------|
| 🏠 **Welcome** | Quick stats, agent overview, quick-start navigation |
| 📄 **JD Management** | Create, save, edit JDs + AI-assisted JD builder |
| 🔍 **Screening** | Step-by-step pipeline: JD → Resumes → Configure → Run |
| 📊 **Results** | Rankings table, stacked bar charts, candidate radar charts |
| 🤖 **Agent Panel** | Per-candidate consensus, individual agent evaluations, discussion log |
| 📅 **History** | Past sessions searchable by date/month/year |
| 📈 **Analytics** | Grade distribution, monthly trends, all-candidates view |
| ❓ **Interview Prep** | Auto-generated questionnaires, DOCX + JSON export |

---

## 🔍 Verification Pipeline

TalentLens cross-references candidate claims against real-world data:

- **🏢 Companies** — OpenCorporates API for registration status, jurisdiction, founding date
- **🔗 LinkedIn** — Profile URL resolution, name cross-check, completeness signals, red flag detection
- **📧 Email** — Format validation, MX record lookup, domain classification
- **📅 Timeline** — Employment gap analysis, experience calculation, date plausibility
- **🆔 Identity** — Cross-reference name, email, LinkedIn, and employment history

---

## ⚙️ Configuration

| Variable | Required | Description |
|:---------|:--------:|:------------|
| `OPENAI_API_KEY` | No | GPT-4o for LLM parsing (heuristic mode works without) |
| `ANTHROPIC_API_KEY` | No | Claude as alternative LLM provider |
| `LLM_PROVIDER` | No | `openai` (default) or `anthropic` |
| `OPENCORPORATES_API_KEY` | No | Higher rate limits for company verification |
| `WEIGHT_*` | No | Override scoring weights (e.g. `WEIGHT_REQUIRED_SKILLS=40`) |

---

## 🛠 Tech Stack

| Layer | Technology |
|:------|:-----------|
| **Language** | Python 3.11+ |
| **Dashboard** | Streamlit + Plotly |
| **NLP** | Sentence-Transformers (all-MiniLM-L6-v2), spaCy, scikit-learn |
| **LLM** | OpenAI GPT-4o / Anthropic Claude (optional) |
| **Storage** | SQLite (history, sessions, JDs) |
| **CLI** | Typer + Rich |
| **Verification** | OpenCorporates API, DNS MX lookups, HTTP resolution |
| **Export** | python-docx (DOCX), JSON, HTML, CSV |
| **CI/CD** | GitHub Actions + taskctl (local) |
| **Code Quality** | Ruff (lint+format), Mypy (types), pytest + pytest-cov |
| **Security** | Bandit (SAST), pip-audit (CVE), Gitleaks (secrets) |
| **Reporting** | Allure, pytest-html, coverage HTML |
| **Git Hooks** | pre-commit (ruff, bandit, mypy, gitleaks, conventional commits) |
| **Containerization** | Docker + Docker Compose |

---

## 🔒 DevSecOps Pipeline

TalentLens ships with a full DevSecOps pipeline that runs **locally** via [taskctl](https://github.com/taskctl/taskctl) and **in CI** via GitHub Actions.

### Pipeline Stages

```mermaid
graph LR
    A["🧹 Clean"] --> B["🔍 Lint"]
    A --> C["📝 Typecheck"]
    A --> D["🛡️ Bandit"]
    A --> E["📦 pip-audit"]
    A --> F["🔑 Gitleaks"]
    B --> G["🧪 Test"]
    C --> G
    D --> G
    E --> G
    F --> G
    G --> H["📊 Report"]

    style A fill:#1e293b,stroke:#6366f1,color:#e2e8f0
    style B fill:#1e293b,stroke:#f59e0b,color:#e2e8f0
    style C fill:#1e293b,stroke:#3b82f6,color:#e2e8f0
    style D fill:#1e293b,stroke:#ef4444,color:#e2e8f0
    style E fill:#1e293b,stroke:#ef4444,color:#e2e8f0
    style F fill:#1e293b,stroke:#ef4444,color:#e2e8f0
    style G fill:#1e293b,stroke:#10b981,color:#e2e8f0
    style H fill:#1e293b,stroke:#8b5cf6,color:#e2e8f0
```

| Stage | Tool | What It Does |
|:------|:-----|:-------------|
| **Lint** | Ruff | Linting (500+ rules) + format enforcement |
| **Typecheck** | MyPy | Static type checking across all modules |
| **SAST** | Bandit | Python security analysis (SQL injection, hardcoded secrets, pickle) |
| **CVE Scan** | pip-audit | Dependency vulnerability scanning against PyPI advisory DB |
| **Secrets** | Gitleaks | Detects API keys, tokens, passwords in source + git history |
| **Test** | pytest | 79 tests across 7 modules with coverage + Allure integration |
| **Report** | Allure | Interactive HTML dashboard with test history and trends |

### Run Locally

```bash
# Install taskctl (macOS)
brew install taskctl

# Full pipeline — lint → security → test → report
taskctl run all

# Quick feedback — lint + test only
taskctl run quick

# Security-only scan
taskctl run security

# Individual stages
taskctl run lint
taskctl run test
taskctl run typecheck
taskctl run bandit
```

### Pipeline Output

After `taskctl run all`, the following reports are generated:

| Report | Path | Description |
|:-------|:-----|:------------|
| 📊 Allure Dashboard | `allure-report/index.html` | Interactive test results with history |
| 📈 Coverage HTML | `htmlcov/index.html` | Line-by-line coverage report |
| 🧪 Test Report | `reports/test-report.html` | Self-contained pytest HTML report |
| 🛡️ Bandit Report | `reports/bandit-report.json` | SAST findings (severity, CWE, location) |
| 📦 pip-audit Report | `reports/pip-audit-report.json` | Dependency CVEs found |
| 🔑 Gitleaks Report | `reports/gitleaks-report.json` | Leaked secrets detected |
| 📉 Coverage JSON | `reports/coverage.json` | Machine-readable coverage data |

```bash
# Open Allure dashboard in browser
allure open allure-report
```

### Pre-Commit Hooks

Git hooks enforce quality on every commit:

```bash
# Install hooks (one-time setup)
pre-commit install
pre-commit install --hook-type commit-msg
```

| Hook | Trigger | What It Catches |
|:-----|:--------|:----------------|
| **Ruff** | pre-commit | Lint violations, auto-fixes safe issues |
| **Ruff Format** | pre-commit | Unformatted Python files |
| **Bandit** | pre-commit | Security issues in changed files |
| **MyPy** | pre-commit | Type errors in changed files |
| **Gitleaks** | pre-commit | Secrets about to be committed |
| **Conventional Commits** | commit-msg | Enforces `feat:`, `fix:`, `docs:` prefixes |
| **File Hygiene** | pre-commit | Trailing whitespace, YAML/TOML/JSON syntax, large files, merge conflicts, private keys |
| **Branch Protection** | pre-commit | Prevents direct commits to `main` |

### GitHub Actions CI

The [CI workflow](.github/workflows/ci.yml) runs on every push to `main`/`develop` and all PRs:

```
┌─────────────────────────────────────────────────────────┐
│                    CI — DevSecOps Pipeline               │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│  Lint    │ Security │ pip-audit│ Gitleaks │  Typecheck  │
│  (Ruff)  │ (Bandit) │  (CVEs)  │ (Secrets)│  (MyPy)    │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│           Test (Python 3.11 / 3.12 / 3.13)              │
│           pytest + coverage + Allure + JUnit             │
├─────────────────────────────────────────────────────────┤
│                 Docker Build (cached)                    │
├─────────────────────────────────────────────────────────┤
│              Allure Report (merged results)              │
└─────────────────────────────────────────────────────────┘
```

All security reports and test artifacts are uploaded as GitHub Actions artifacts for download.

### Test Suite

<!-- BEGIN TEST STATS -->
| Metric | Value |
|:-------|:------|
| **Total Tests** | 79 |
| **Test Files** | 7 |
| **Pass Rate** | 100% |
| **Coverage** | 25.5% |
<!-- END TEST STATS -->

| Test Module | Tests | What It Covers |
|:------------|:-----:|:---------------|
| `test_pipeline.py` | 19 | Pipeline state machine: stages, transitions, batch ops, audit trail |
| `test_red_flags.py` | 13 | Employment gaps, job hopping, title inflation, email/education risk |
| `test_comparator.py` | 12 | Multi-candidate comparison matrix, radar data, stack ranking |
| `test_history.py` | 9 | Session CRUD, JD management, statistics summary |
| `test_archetypes.py` | 9 | Role classification: cloud, data, management archetypes |
| `test_export_engine.py` | 7 | MD/JSON/HTML export, comparative reports, executive summary |
| `test_jd_quality.py` | 6 | JD analysis: dimensions, word count, red flags, strengths |

---

## 🐳 Docker

```bash
# Quick start with Docker Compose
docker compose up --build -d

# Or build manually
docker build -t talentlens:latest .
docker run -p 8503:8503 --env-file .env talentlens:latest
```

---

## 🧑‍💻 Development

```bash
# Install dependencies
pip install -r requirements.txt

# Install dev tools
pip install ruff mypy bandit "bandit[toml]" pip-audit pytest pytest-cov pytest-html allure-pytest

# Install pre-commit hooks
pre-commit install && pre-commit install --hook-type commit-msg

# Full local pipeline (lint + security + test + report)
taskctl run all

# Quick feedback loop (lint + test)
taskctl run quick

# Run tests only
python -m pytest tests/ -v

# Start dashboard
streamlit run dashboard_v3.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full development guide.

---

## 📄 License

MIT — use it, fork it, build on it. See [LICENSE](LICENSE).

---

<div align="center">

**Built with curiosity and too much coffee.** ☕

*If TalentLens helped you, consider giving it a ⭐*

</div>
