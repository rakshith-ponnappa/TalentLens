# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 3.x     | Yes       |
| < 3.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in TalentLens, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email: rakshith-ponnappa@users.noreply.github.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will acknowledge receipt within 48 hours and aim to release a fix within 7 days for critical issues.

## Security Practices

### Data Handling
- **Resumes and JDs** are processed locally and never transmitted to external services (except when using LLM APIs with explicit user consent)
- **Heuristic mode** processes everything locally with zero external calls
- **SQLite database** stores only session metadata, not full resume content
- **Uploaded files** are excluded from git via `.gitignore`

### Secret Management
- All API keys stored in `.env` (gitignored)
- No hardcoded secrets in source code
- CI pipeline scans for accidental secret commits via `detect-private-key` pre-commit hook

### Dependencies
- Dependencies pinned with minimum versions in `requirements.txt`
- `bandit` security scanner runs in CI and pre-commit
- Dependabot can be enabled for automated vulnerability alerts

### SQL Injection Prevention
- All database queries in `history.py` use parameterized statements
- No string concatenation for SQL queries

### Input Validation
- File uploads restricted to `.docx` and `.pdf` extensions
- Pydantic models validate all structured data
- User inputs sanitized at system boundaries
