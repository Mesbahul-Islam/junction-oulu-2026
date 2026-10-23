# Shortcuts. Run `make help` to list them. Every target is a plain command you
# can also copy into a terminal (see docs/GUIDE.md if you don't have make).

PY := .venv/bin/python
MANAGE := cd backend && ../$(PY) manage.py

.DEFAULT_GOAL := help
.PHONY: help env up down logs reset shell-docker install bootstrap run worker test pipeline

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

env:  ## Create .env from .env.example (won't overwrite)
	@test -f .env || cp .env.example .env

# --- Docker (recommended) -------------------------------------------------
up: env  ## Start the whole stack in Docker (migrates + seeds automatically)
	docker compose up --build -d
	@echo "API docs: http://localhost:8000/api/docs/   Admin: http://localhost:8000/admin/"

down:  ## Stop the Docker stack (keeps the database)
	docker compose down

logs:  ## Follow logs of web, worker and beat
	docker compose logs -f web worker beat

reset:  ## Stop the stack AND delete the database volume, then start fresh
	docker compose down -v
	$(MAKE) up

shell-docker:  ## Django shell inside the web container
	docker compose exec web python manage.py shell

# --- Local, without Docker (SQLite, tasks run inline) ---------------------
install: env  ## Create .venv and install dependencies
	python3 -m venv .venv
	$(PY) -m pip install -r backend/requirements.txt

bootstrap:  ## Migrate, seed demo data, create admin (local)
	$(MANAGE) bootstrap

run:  ## Run the dev server locally on :8000
	$(MANAGE) runserver

worker:  ## Run a Celery worker locally (needs Redis and CELERY_TASK_ALWAYS_EAGER=False)
	cd backend && ../.venv/bin/celery -A config worker -l info

test:  ## Run the test suite
	cd backend && ../.venv/bin/pytest -q

pipeline:  ## Run the AI newsroom once for the Oulu community (local)
	$(MANAGE) run_pipeline oulu
