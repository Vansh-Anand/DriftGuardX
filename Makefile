.PHONY: help install install-dev env migrate seed lint typecheck format test test-unit test-integration test-e2e test-security golden-demo build-api build-web up down logs clean

PYTHON := python3
PIP := pip
API_DIR := apps/api
WEB_DIR := apps/web

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ─── Setup ───────────────────────────────────────────────────────────────────
env: ## Copy .env.example to .env (will not overwrite)
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env — fill in secrets before use"; else echo ".env already exists"; fi

install: ## Install production Python deps
	$(PIP) install -r requirements.txt

install-dev: ## Install all Python deps (including dev/test)
	$(PIP) install -r requirements.txt -r requirements-dev.txt
	cd $(API_DIR) && pip install -e .

install-web: ## Install Node.js deps for the web console
	cd $(WEB_DIR) && npm install

# ─── Database ────────────────────────────────────────────────────────────────
migrate: ## Run Alembic migrations (upgrade to head)
	cd $(API_DIR) && alembic upgrade head

migrate-down: ## Rollback last migration
	cd $(API_DIR) && alembic downgrade -1

migrate-status: ## Show migration status
	cd $(API_DIR) && alembic current

seed: ## Seed the database with demo data
	$(PYTHON) -m apps.api.src.scripts.seed

# ─── Linting & Formatting ────────────────────────────────────────────────────
lint: ## Run ruff linter
	ruff check apps/ packages/ tests/

format: ## Run black formatter
	black apps/ packages/ tests/

format-check: ## Check formatting without changing files
	black --check apps/ packages/ tests/

typecheck: ## Run mypy type checks
	mypy apps/ packages/ --ignore-missing-imports

security-scan: ## Run bandit security scan
	bandit -r apps/ packages/ -ll

# ─── Testing ─────────────────────────────────────────────────────────────────
test: ## Run all tests
	pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	pytest tests/ -v -m unit --tb=short

test-integration: ## Run integration tests (require DB + Redis)
	pytest tests/ -v -m integration --tb=short

test-contract: ## Run schema/contract tests
	pytest tests/ -v -m contract --tb=short

test-security: ## Run security tests
	pytest tests/ -v -m security --tb=short

test-e2e: ## Run end-to-end tests
	pytest tests/ -v -m e2e --tb=short

# ─── Demo ─────────────────────────────────────────────────────────────────────
golden-demo: ## Run the golden end-to-end demonstration
	$(PYTHON) examples/golden_demo.py

# ─── Docker Compose ───────────────────────────────────────────────────────────
up: ## Start the full stack (build if needed)
	docker compose -f infra/docker-compose.yml up --build

up-detach: ## Start the full stack detached
	docker compose -f infra/docker-compose.yml up --build -d

down: ## Stop the full stack
	docker compose -f infra/docker-compose.yml down

down-volumes: ## Stop and remove volumes (DESTROYS DATA)
	docker compose -f infra/docker-compose.yml down -v

logs: ## Tail logs for all services
	docker compose -f infra/docker-compose.yml logs -f

logs-api: ## Tail API logs
	docker compose -f infra/docker-compose.yml logs -f api

# ─── Web Console ──────────────────────────────────────────────────────────────
dev-web: ## Start Next.js dev server
	cd $(WEB_DIR) && npm run dev

build-web: ## Build Next.js production bundle
	cd $(WEB_DIR) && npm run build

# ─── API Dev ──────────────────────────────────────────────────────────────────
dev-api: ## Start FastAPI dev server with hot reload
	cd $(API_DIR) && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# ─── Clean ────────────────────────────────────────────────────────────────────
clean: ## Remove build artifacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

ci: lint format-check typecheck security-scan test ## Full CI pipeline
