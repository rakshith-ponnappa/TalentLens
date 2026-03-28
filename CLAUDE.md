# CLAUDE.md

This file provides guidance to Claude Code when working with TalentLens.

## Project Overview

TalentLens is a **multi-agent AI resume screening pipeline** with a Streamlit dashboard.
It evaluates candidates using 11 specialist AI agents (Cloud Architect, Security, HR, etc.),
hybrid NLP scoring (TF-IDF + SBERT + Jaccard), background verification, and interview prep.

## Running Tests

```bash
# Run the full E2E test (requires sample data in data/)
python test_e2e.py

# Run heuristic tests
python _test_heuristic.py

# Run identity verification tests
python _test_identity.py

# Lint + format (requires pre-commit)
pre-commit run --all-files

# Type check
mypy --ignore-missing-imports *.py

# Security scan
bandit -r . --exclude .venv,__pycache__
```

## Architecture

```
resume-screener/
├── main.py              — CLI entry point (Typer)
├── dashboard_v3.py      — Streamlit dashboard (8 pages, TalentLens branding)
├── config.py            — Config loader (.env, weights validation)
├── models.py            — Pydantic data models (Candidate, JD, Score, etc.)
├── jd_analyzer.py       — Job description parser (DOCX → structured JD)
├── resume_parser.py     — Resume parser (PDF/DOCX → Candidate model)
├── heuristics.py        — Zero-LLM heuristic mode (regex, rules, NLP)
├── scorer.py            — Hybrid scoring engine (TF-IDF + SBERT + Jaccard)
├── agents.py            — 11 AI agent personas with weighted consensus
├── verifier.py          — Verification orchestrator
├── verifier_company.py  — Company verification (OpenCorporates)
├── verifier_certs.py    — Certification verification
├── verifier_linkedin.py — LinkedIn profile validation
├── verifier_identity.py — Identity cross-referencing
├── history.py           — SQLite session persistence
├── interview_gen.py     — Interview questionnaire generator + DOCX export
├── report_generator.py  — PDF/text report generation
├── llm_client.py        — LLM abstraction (OpenAI / Anthropic)
├── data/                — Resumes, JDs, SQLite DB (gitignored)
└── output/              — Generated reports (gitignored)
```

## Key Design Decisions

- **11 agents** with distinct weights summing to 1.0 — never change the sum
- **Heuristic mode** enables the full pipeline without API keys
- **Scoring weights** must sum to 100 (required=35, preferred=15, experience=25, education=10, certs=10, semantic=5)
- **SQLite** for history — no external database dependency
- **Streamlit** dashboard runs on port 8503 with `--server.address 0.0.0.0`

## Development Notes

- Python 3.11+ required, developed on 3.14
- Virtual env at `../.venv/` (parent directory)
- Use `ruff` for linting/formatting, `bandit` for security, `mypy` for types
- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`
- All user inputs are validated at system boundaries (Pydantic models)
- Never hardcode API keys — always use `.env` + `python-dotenv`
- Keep files focused: <800 lines, functions <50 lines
- Test with `python test_e2e.py` after changes

## Security

- No hardcoded secrets — `.env` for all keys
- All file uploads validated (DOCX/PDF only)
- SQL injection prevented via parameterized queries in `history.py`
- XSS mitigated by Streamlit's built-in escaping
- Sensitive data (resumes, JDs, reports) excluded from git via `.gitignore`

## The 11 Agents

| Agent | Weight | Focus |
|-------|--------|-------|
| Cloud Solutions Architect | 14% | Architecture, scalability, cloud design |
| AWS Migration Engineer | 12% | Migration experience, AWS services |
| Security Architect | 10% | Security posture, compliance, IAM |
| Cloud Operations Engineer | 10% | Monitoring, IaC, CI/CD, automation |
| HR Manager | 10% | Culture fit, career trajectory, soft skills |
| Application Architect | 8% | App design, microservices, APIs |
| SRE Engineer | 8% | Reliability, SLOs, incident response |
| AWS Platform Engineer | 8% | Platform engineering, Kubernetes, EKS |
| Recruiting Engineer | 8% | Technical depth validation |
| Product Owner | 6% | Business alignment, stakeholder management |
| QA Architect | 6% | Testing strategy, quality frameworks |
