.PHONY: start install check-dev-environment test test-backend test-frontend db-upgrade db-current ingest-market-data audit-market-data generate-market-environment generate-sector-ranking generate-candidates generate-trade-plans dev-api dev-web

start:
	bash start.sh

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -U pip
	.venv/bin/pip install -e ".[dev]"
	cd frontend && npm install

check-dev-environment:
	bash scripts/check-dev-environment.sh

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

generate-sector-ranking:
	bash scripts/generate-sector-ranking.sh

generate-candidates:
	bash scripts/generate-candidates.sh

generate-trade-plans:
	bash scripts/generate-trade-plans.sh

dev-api:
	bash scripts/dev-api.sh

dev-web:
	bash scripts/dev-web.sh
