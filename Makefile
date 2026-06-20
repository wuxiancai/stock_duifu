.PHONY: install test test-backend test-frontend dev-api dev-web

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

dev-api:
	bash scripts/dev-api.sh

dev-web:
	bash scripts/dev-web.sh

