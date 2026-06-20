.PHONY: install test test-backend test-frontend db-upgrade db-current ingest-market-data audit-market-data generate-market-environment dev-api dev-web

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

audit-market-data:
	bash scripts/audit-market-data.sh

generate-market-environment:
	bash scripts/generate-market-environment.sh

dev-api:
	bash scripts/dev-api.sh

dev-web:
	bash scripts/dev-web.sh
