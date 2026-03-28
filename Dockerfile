FROM python:3.12-slim AS base

LABEL maintainer="Rakshith Ponnappa"
LABEL description="TalentLens — Multi-agent AI resume screening pipeline"

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for PDF/DOCX parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# ── Dependencies layer (cached unless requirements change) ───────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application code ────────────────────────────────────────────
COPY *.py ./
COPY data/.gitkeep data/

# Create directories for runtime data
RUN mkdir -p data/resumes data/jds output

# ── Health check ────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8503/_stcore/health || exit 1

EXPOSE 8503

# ── Run the dashboard ───────────────────────────────────────────
CMD ["streamlit", "run", "dashboard_v3.py", \
     "--server.port=8503", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
