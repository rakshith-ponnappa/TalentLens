.PHONY: help install dev lint format typecheck security test dashboard docker clean

# Default target
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────
install: ## Install production dependencies
	pip install -r requirements.txt

dev: ## Install dev dependencies + pre-commit hooks
	pip install -r requirements.txt
	pip install -e ".[dev]"
	pre-commit install
	pre-commit install --hook-type commit-msg

# ── Code Quality ─────────────────────────────────────────────────
lint: ## Run ruff linter
	ruff check .

format: ## Auto-format code with ruff
	ruff check --fix .
	ruff format .

typecheck: ## Run mypy type checker
	mypy --ignore-missing-imports *.py

security: ## Run bandit security scanner
	bandit -c pyproject.toml -r . --exclude .venv,__pycache__

pre-commit: ## Run all pre-commit hooks
	pre-commit run --all-files

# ── Testing ──────────────────────────────────────────────────────
test: ## Run all tests
	python _test_heuristic.py
	python _test_identity.py

test-e2e: ## Run E2E test (requires sample data)
	python test_e2e.py

# ── Run ──────────────────────────────────────────────────────────
dashboard: ## Start the Streamlit dashboard
	streamlit run dashboard_v3.py --server.port 8503 --server.headless true

dashboard-network: ## Start dashboard accessible on network
	streamlit run dashboard_v3.py --server.port 8503 --server.address 0.0.0.0 --server.headless true

cli: ## Run the CLI tool
	python main.py

# ── Docker ───────────────────────────────────────────────────────
docker: ## Build and run with Docker Compose
	docker compose up --build -d

docker-build: ## Build Docker image only
	docker build -t talentlens:latest .

docker-stop: ## Stop Docker containers
	docker compose down

# ── Maintenance ──────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .mypy_cache .ruff_cache .pytest_cache
	rm -rf dist build *.egg-info
