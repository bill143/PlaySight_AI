# PlaySight AI - developer tasks.
# Works with GNU make on Linux/macOS/Windows (Git Bash / GnuWin).
# Scripts in scripts/ mirror these targets for shells without make.

PYTHON ?= python
VIDEO ?= data/demo/demo_match.mp4
MATCH_ID ?=

.PHONY: install lint fmt typecheck test api worker dashboard up down seed process

install: ## Install the package with dev extras (editable)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[dev]"

lint: ## Ruff + Black checks
	ruff check src tests
	black --check src tests

fmt: ## Auto-format (Black) and fix lint (Ruff)
	ruff check --fix src tests
	black src tests

typecheck: ## mypy on the package
	mypy src/playsight

test: ## Run tests (excluding heavy CV tests)
	pytest -m "not cv"

api: ## Run the FastAPI app locally (reload)
	uvicorn playsight.api.main:app --host 0.0.0.0 --port 8000 --reload

worker: ## Run a Celery worker locally
	celery -A playsight.jobs.celery_app worker --loglevel=INFO

dashboard: ## Run the Next.js dashboard dev server
	cd dashboard && npm run dev

up: ## Start the full docker-compose stack
	docker compose up --build -d

down: ## Stop the docker-compose stack
	docker compose down

seed: ## Init DB and seed demo data (club/team/players + synthetic video)
	playsight init-db
	playsight seed-demo

process: ## Process a video end-to-end: make process VIDEO=path MATCH_ID=id
	playsight process "$(VIDEO)" $(if $(MATCH_ID),--match-id $(MATCH_ID),)
