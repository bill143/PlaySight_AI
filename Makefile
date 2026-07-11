.DEFAULT_GOAL := help

.PHONY: help dev down backend-install migrate lint format test test-cov dashboard-install dashboard-dev worker beat clean

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "; print "Available targets:"} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

dev: ## Start the local development stack
	docker compose up --build

down: ## Stop the local development stack
	docker compose down

backend-install: ## Install backend dependencies into the active virtualenv
	pip install -r backend/requirements.txt -r backend/requirements-dev.txt

migrate: ## Apply database migrations
	alembic -c backend/alembic.ini upgrade head

lint: ## Run backend and dashboard lint checks
	ruff check backend/ tests/ && cd dashboard && npm run lint

format: ## Format backend code and apply safe Ruff fixes
	black backend/ tests/ && ruff check --fix backend/ tests/

test: ## Run the test suite
	python -m pytest tests/ -v --tb=short

test-cov: ## Run tests with backend coverage output
	pytest tests/ --cov=backend --cov-report=term-missing

dashboard-install: ## Install dashboard dependencies
	cd dashboard && npm install

dashboard-dev: ## Start the Next.js dashboard locally
	cd dashboard && npm run dev

worker: ## Run the Celery worker locally
	celery -A backend.workers.celery_app worker --loglevel=info

beat: ## Run the Celery beat scheduler locally
	celery -A backend.workers.celery_app beat --loglevel=info

clean: ## Remove common local cache directories
	find . -type d \( -name '__pycache__' -o -name '.pytest_cache' -o -name '.ruff_cache' \) -prune -exec rm -rf {} +
