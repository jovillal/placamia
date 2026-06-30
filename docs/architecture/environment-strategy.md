# Environment Strategy

## Purpose

This document defines how PlacamIA handles local, test, and production
configuration.

The goal is to keep the same codebase across environments while changing only
runtime configuration.

## Current Approach

PlacamIA uses local-first development.

The backend runs from `apps/api`, reads settings from environment variables, and
loads `apps/api/.env` during local development.

## Environment Progression

1. local
2. test
3. production

## Configuration Rules

- Use the same codebase in every environment.
- Use environment variables for environment-specific configuration.
- Do not commit real `.env` files.
- Keep local example values in `apps/api/.env.example`.
- Do not hardcode secrets, credentials, tokens, or production URLs.
- Do not add environment-specific business logic.
- Use Alembic for database schema changes.

## Local Environment

Local development uses:

- Python 3.12+
- a virtual environment at `apps/api/.venv`
- PostgreSQL from `infra/docker/docker-compose.yml`
- configuration from `apps/api/.env`
- backend commands from the repository `Makefile`

Recommended local setup:

```bash
cd apps/api
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cd ../..
cp apps/api/.env.example apps/api/.env
docker compose -f infra/docker/docker-compose.yml up -d
make migrate
make dev
```

## Test Environment

Tests must be executable locally without PostgreSQL or external services.

The current pytest suite uses in-memory SQLite databases and FastAPI dependency
overrides for route tests. This keeps tests deterministic and fast while still
checking repository, service, endpoint, authentication, authorization, and
security baseline behavior.

Run tests with:

```bash
make test
```

## Production Environment

Production deployment is out of scope for the current foundation task.

Future production configuration must still follow these rules:

- provide secrets through the runtime environment or a secret manager
- use PostgreSQL
- run Alembic migrations intentionally
- keep SQL echo logging disabled unless needed for a controlled investigation
- require HTTPS for public traffic
- avoid storing payment card data

## Environment Variables

| Variable | Required Locally | Purpose |
| --- | --- | --- |
| `APP_NAME` | Yes | FastAPI application title. |
| `ENV` | Yes | Environment label. |
| `DATABASE_URL` | Yes for local runtime | SQLAlchemy connection URL. |
| `SQLALCHEMY_ECHO` | Yes | SQL logging flag; defaults should remain `false`. |
| `AUTH_TOKEN_SECRET` | Yes for protected endpoints | Token signing and verification secret. |

`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` are documented in
`apps/api/.env.example` to mirror the local PostgreSQL container. The runtime
connection currently uses `DATABASE_URL`.

## Command Summary

| Command | Environment | Purpose |
| --- | --- | --- |
| `make dev` | local | Start the FastAPI backend. |
| `make test` | test | Run pytest locally without external services. |
| `make migrate` | local | Apply Alembic migrations to the configured database. |
| `make migration m="message"` | local | Generate a migration with Alembic autogenerate. |
| `make seed` | local | Seed catalog data for development. |
