.PHONY: install test test-backend test-frontend db-upgrade db-current ingest-market-data dev-api dev-web

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -U pip
	.venv/bin/pip install -e ".[dev]"
	cd frontend && npm install

test: test-backend test-frontend

test-backend:
	.venv/bin/pytest

test-frontend:
	cd frontend && npm test -- --run

db-upgrade:
	bash scripts/db-upgrade.sh

db-current:
	bash scripts/db-current.sh

ingest-market-data:
	bash scripts/ingest-market-data.sh

dev-api:
	bash scripts/dev-api.sh

dev-web:
	bash scripts/dev-web.sh
