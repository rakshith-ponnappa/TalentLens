# Changelog

All notable changes to TalentLens will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Conventional Commits](https://www.conventionalcommits.org/).

## [3.0.0] — 2026-03-29

### Added
- Project governance: CLAUDE.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md
- CI/CD pipeline: GitHub Actions (lint, security, typecheck, test, Docker build)
- Release workflow: auto-generate changelog on tag push
- Pre-commit hooks: ruff (lint + format), bandit (security), conventional commits
- Docker support: Dockerfile + docker-compose.yml with health checks
- Makefile with 15+ developer workflow commands
- pyproject.toml with unified tool configuration (ruff, mypy, bandit, pytest, coverage)
- PR template + issue templates (bug report, feature request)
- LICENSE (MIT)

### Changed
- Rebranded from "Resume Screener Pro" to "TalentLens — See beyond the resume"
- Dashboard v3 with glassmorphism UI, hero headers, gradient accents
- README completely rewritten with Mermaid architecture diagram, badges, tables
- .env.template cleaned up (no placeholder secrets)
- .gitignore expanded for tool caches

## [2.0.0] — 2026-03-28

### Added
- 11-agent evaluation panel (up from 7) with weighted consensus
- Cloud-focused agents: Cloud Solutions Architect, AWS Migration Engineer, Cloud Ops, AWS Platform
- Dashboard v3 with 8 pages: Welcome, JD Management, Screening, Results, Agent Panel, History, Analytics, Interview Prep
- Interview questionnaire generator with DOCX export
- SQLite history persistence with session tracking
- Heuristic mode: full pipeline without API keys
- Background verification: company, LinkedIn, identity, certifications
- TF-IDF + SBERT + Jaccard hybrid scoring across 6 dimensions

### Fixed
- Name extraction: blocklist for "CURRICULUM VITAE", location detection, email fallback
- Experience parsing: expanded date formats, text-based fallback
- Agent weights corrected to sum exactly to 1.0
