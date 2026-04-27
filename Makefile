SHELL := /bin/bash

API_DIR := apps/api

dev:
	./scripts/dev.sh

test:
	cd $(API_DIR) && . .venv/bin/activate && pytest

migrate:
	cd $(API_DIR) && . .venv/bin/activate && alembic upgrade head

seed:
	cd $(API_DIR) && . .venv/bin/activate && PYTHONPATH=. python ../../scripts/seed_catalog.py

migration:
	cd $(API_DIR) && . .venv/bin/activate && alembic revision --autogenerate -m "$(m)"

downgrade:
	cd $(API_DIR) && . .venv/bin/activate && alembic downgrade -1
