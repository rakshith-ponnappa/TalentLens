# Resume Screener

End-to-end pipeline: parse JD → parse resumes → score & rank → verify background/LinkedIn/certs → export report.

## Setup

```bash
cd resume-screener
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm             # optional NLP model

cp .env.template .env
# edit .env – add your OPENAI_API_KEY (required)
```

## Workflow

### Step 1 – Load a Job Description

```bash
# From a file (PDF, DOCX, or TXT)
python main.py jd path/to/job_description.pdf

# Paste as raw text
python main.py jd "We are looking for a Senior DevOps Engineer with 5+ years ..."
```

### Step 2 – Screen Resumes

```bash
python main.py screen resume1.pdf resume2.pdf resume3.docx

# Show full per-candidate detail
python main.py screen resume1.pdf resume2.pdf --detail

# Top 5 only, skip background checks
python main.py screen *.pdf --top 5 --no-verify
```

### Combined (one command)

```bash
python main.py run --jd jd.pdf --resume r1.pdf --resume r2.pdf --detail
```

### Full detail for one candidate

```bash
python main.py detail-cmd resume.pdf
```

## Output

- **Terminal** – ranked table + per-candidate detail
- **JSON** – `output/screening_YYYYMMDD_HHMMSS.json`

## Scoring weights (default)

| Component         | Weight |
|-------------------|--------|
| Required skills   | 35 pts |
| Preferred skills  | 15 pts |
| Experience years  | 25 pts |
| Education level   | 10 pts |
| Certifications    | 10 pts |
| Semantic match    |  5 pts |

Adjust via `.env`: `WEIGHT_REQUIRED_SKILLS`, `WEIGHT_EXPERIENCE`, etc.  Must sum to 100.

## Verification

### Companies
- **OpenCorporates** (free public API) – registration status, jurisdiction, founding date
- **LinkedIn Company page** – existence check via public URL resolution

### Certifications
- Matched against `data/cert_registry.json` (30+ major certs)
- Credly org page verified
- Direct verification URLs provided for HR follow-up

### LinkedIn Profile
- URL resolution (200 OK, no authwall redirect)
- Name on profile vs resume cross-check
- Profile completeness signals (photo, headline, connections)
- Red flag detection (auto-generated slug, name mismatch, missing photo)

## Architecture

```
main.py               CLI entry point (typer)
jd_analyzer.py        JD → JDCriteria   (LLM)
resume_parser.py      PDF/DOCX → CandidateProfile  (LLM)
scorer.py             skill match + experience + education + certs + semantic
verifier.py           orchestrates all verification
  verifier_company.py   OpenCorporates + LinkedIn company page
  verifier_certs.py     cert registry + Credly check
  verifier_linkedin.py  LinkedIn public profile check
report_generator.py   rich terminal output + JSON export
llm_client.py         OpenAI / Anthropic wrapper
config.py             .env loader
models.py             dataclasses
data/cert_registry.json   30+ certifications with verification URLs
output/               reports saved here
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes (if using OpenAI) | GPT-4o used for parsing |
| `ANTHROPIC_API_KEY` | Yes (if using Anthropic) | Claude used for parsing |
| `LLM_PROVIDER` | No | `openai` (default) or `anthropic` |
| `OPENCORPORATES_API_KEY` | No | Increases OpenCorporates rate limit |
| `WEIGHT_*` | No | Scoring weight overrides |
