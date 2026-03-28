# Contributing to TalentLens

Thanks for your interest in contributing! TalentLens is a community-driven project.

## Table of Contents

- [Quick Start](#quick-start)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Commit Convention](#commit-convention)
- [Pull Request Process](#pull-request-process)
- [Architecture Guide](#architecture-guide)

---

## Quick Start

```bash
# 1. Fork and clone
gh repo fork rakshith-ponnappa/TalentLens --clone
cd TalentLens

# 2. Set up development environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
pip install -e ".[dev]"

# 3. Install pre-commit hooks
pre-commit install
pre-commit install --hook-type commit-msg

# 4. Create a branch
git checkout -b feat/your-feature

# 5. Make changes, test, commit
pre-commit run --all-files
python _test_heuristic.py
git add . && git commit -m "feat: your feature description"
git push -u origin feat/your-feature
```

---

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- (Optional) Docker for containerized dev

### Environment Variables

Copy `.env.template` to `.env` and fill in your keys:

```bash
cp .env.template .env
```

The heuristic mode works without any API keys — perfect for development.

### Running the Dashboard

```bash
streamlit run dashboard_v3.py --server.port 8503
```

### Running Tests

```bash
# Heuristic tests
python _test_heuristic.py

# Identity verification tests
python _test_identity.py

# Full E2E (requires sample data)
python test_e2e.py
```

---

## Code Style

We use **ruff** for linting and formatting (configured in `pyproject.toml`):

- **Line length:** 120 characters
- **Quote style:** Double quotes
- **Imports:** Sorted by isort rules
- **Target:** Python 3.11+

```bash
# Check lint issues
ruff check .

# Auto-fix lint issues
ruff check --fix .

# Format code
ruff format .
```

### Guidelines

| Do | Don't |
|----|-------|
| Keep functions < 50 lines | Create god-functions |
| Keep files < 800 lines | Dump everything in one file |
| Validate inputs at boundaries | Trust external data |
| Use parameterized SQL queries | Concatenate SQL strings |
| Store secrets in `.env` | Hardcode API keys |
| Return new objects | Mutate existing state |

---

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>

[optional body]
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, no logic change |
| `refactor` | Code restructuring |
| `perf` | Performance improvement |
| `test` | Adding/updating tests |
| `chore` | Maintenance / tooling |
| `ci` | CI/CD changes |
| `build` | Build system changes |

### Examples

```
feat: add certification verification via Credly API
fix: handle missing email in name extraction fallback
docs: update agent weights table in README
test: add edge case tests for date parsing
ci: add Python 3.13 to test matrix
```

---

## Pull Request Process

1. **Create a branch** from `main` with a descriptive name (`feat/`, `fix/`, `docs/`)
2. **Make focused changes** — one feature or fix per PR
3. **Run pre-commit hooks**: `pre-commit run --all-files`
4. **Run tests**: `python _test_heuristic.py && python _test_identity.py`
5. **Push** and open a PR against `main`
6. **Fill out the PR template** completely
7. **Address review feedback** if requested

### PR Title Format

```
feat: add new verification endpoint
fix: correct experience calculation for overlapping dates
docs: add Docker deployment guide
```

---

## Architecture Guide

### Adding a New Agent

Edit `agents.py`:

1. Add your agent to the `AGENT_PERSONAS` list with:
   - `name`, `role`, `focus_areas`, `weight`
2. **Critical:** Ensure all weights sum to exactly 1.0
3. Update `CLAUDE.md` and `README.md` agent tables

### Adding a New Verifier

1. Create `verifier_<name>.py` following the pattern in `verifier_company.py`
2. Add a `run_<name>_verification()` function returning a structured result
3. Wire it into `verifier.py` orchestrator

### Adding a Dashboard Page

Edit `dashboard_v3.py`:

1. Add your page to the sidebar navigation dict
2. Create a `render_<page>()` function
3. Follow the glassmorphism card pattern for consistent styling

### Modifying Scoring

Edit `scorer.py`:

1. Add new dimension to `Weights` in `config.py`
2. Ensure all weights still sum to 100
3. Update `score_candidate()` to incorporate the new dimension
4. Add tests in `_test_heuristic.py`

---

## Security

- **Never** commit API keys, tokens, or secrets
- **Always** use `.env` for sensitive configuration
- **Always** use parameterized queries for database operations
- **Always** validate file uploads (DOCX/PDF types only)
- Run `bandit -r .` before submitting PRs with security-sensitive changes

---

## Questions?

- [Open an issue](https://github.com/rakshith-ponnappa/TalentLens/issues)
- Check existing issues and discussions

Thanks for contributing! 🔍
