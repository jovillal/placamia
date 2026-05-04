# PlacamIA API

Backend service for PlacamIA.

## Responsibilities

- expose API endpoints
- manage domain logic
- persist core entities
- support template/design customization flows
- prepare for pricing, quoting, checkout, orders, and order tracking

## Stack

- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- pytest

## Setup

From the repository root:

```bash
cd apps/api
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
cd ../..
cp apps/api/.env.example apps/api/.env
```

Start local PostgreSQL before running the API:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
make migrate
```

## Run

```bash
make dev
```

The API is available at `http://localhost:8000`.

## Test

```bash
make test
```

Tests run locally without PostgreSQL.

## Configuration

Local configuration is read from `apps/api/.env`.

Use `apps/api/.env.example` as the template. Real secrets must not be committed.

Required runtime settings:

- `APP_NAME`
- `DATABASE_URL`
- `SQLALCHEMY_ECHO`
- `AUTH_TOKEN_SECRET`

## Migrations

Apply migrations:

```bash
make migrate
```

Generate a migration:

```bash
make migration m="describe change"
```
