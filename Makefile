PYTHON := ./.venv/bin/python
PIP := ./.venv/bin/pip
DRAMATIQ := ./.venv/bin/dramatiq

.PHONY: venv install lock install-locked api web worker inbound-scheduler test lint migrate seed migrate-staging seed-staging api-staging worker-staging compose-up compose-down

venv:
	python3 -m venv .venv

install: venv
	$(PIP) install -e ".[dev]"
	npm --prefix apps/web install

lock:
	./.venv/bin/pip-compile pyproject.toml -o requirements.lock --strip-extras

install-locked:
	./.venv/bin/pip install -r requirements.lock

api:
	$(PYTHON) -m uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000

web:
	npm --prefix apps/web run dev

worker:
	$(DRAMATIQ) apps.worker.worker_app.tasks

inbound-scheduler:
	$(PYTHON) -m apps.worker.worker_app.scheduler

test:
	$(PYTHON) -m pytest
	npm --prefix apps/web run test

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m black --check .
	$(PYTHON) -m mypy apps/api
	npm --prefix apps/web run lint

migrate:
	$(PYTHON) -m alembic upgrade head

seed:
	PYTHONPATH=. $(PYTHON) infrastructure/scripts/seed_sample_data.py

migrate-staging:
	set -a; . ./.env.staging.example; set +a; $(PYTHON) -m alembic upgrade head

seed-staging:
	set -a; . ./.env.staging.example; set +a; APP_ENV=development PYTHONPATH=. $(PYTHON) infrastructure/scripts/seed_sample_data.py

api-staging:
	set -a; . ./.env.staging.example; set +a; $(PYTHON) -m uvicorn apps.api.app.main:app --host 127.0.0.1 --port 8011

worker-staging:
	set -a; . ./.env.staging.example; set +a; $(DRAMATIQ) apps.worker.worker_app.tasks

compose-up:
	docker compose -f infrastructure/docker/docker-compose.yml up -d

compose-down:
	docker compose -f infrastructure/docker/docker-compose.yml down
