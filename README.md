# PlacamIA

PlacamIA is a mobile-first application that allows users to design, quote, and purchase industrial safety signage using templates and rules-based customization.

## Current phase
Backend foundation:

- repository structure
- FastAPI backend
- local PostgreSQL
- SQLAlchemy models
- Alembic migrations
- pytest test suite
- architecture and API documentation

AI-assisted generation is out of scope for the MVP.

## Monorepo structure

```text
apps/
  api/        FastAPI backend
  mobile/     Future mobile application
docs/
  api/
  architecture/
  flows/
  planning/
  product/
infra/
  docker/     Local PostgreSQL compose file
scripts/
.github/
```

## Prerequisites

- Python 3.12+
- Docker with Docker Compose for the local PostgreSQL database
- `make`

The backend Python virtual environment is expected at `apps/api/.venv`.

## Local setup

Create the backend virtual environment and install dependencies:

```bash
cd apps/api
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
```

Create the local environment file:

```bash
cp apps/api/.env.example apps/api/.env
```

The example values are for local development only. Do not commit real secrets or
local `.env` files.

Start the local PostgreSQL database:

```bash
docker compose -f infra/docker/docker-compose.yml up -d
```

If Docker reports `permission denied while trying to connect to the docker API`,
run the command with `sudo` once or add your user to the `docker` group:

```bash
sudo usermod -aG docker "$USER"
```

Then log out and back in before retrying without `sudo`.

The local database is published on host port `54322` to avoid colliding with
other local PostgreSQL projects that commonly use `5432`. If Docker reports
that port `54322` is already in use, another local service is already listening
there. Check it with:

```bash
sudo ss -ltnp 'sport = :54322'
```

Use one of these options:

- Use the existing local PostgreSQL server and create the `placamia` database
  and user there, then update `apps/api/.env`.
- Change the Docker Compose host port mapping, then update `apps/api/.env` so
  `DATABASE_URL` and `DB_PORT` use the same host port.

Apply migrations:

```bash
make migrate
```

Optional seed data:

```bash
make seed
```

## Run the backend

```bash
make dev
```

The API runs with Uvicorn on:

```text
http://localhost:8000
```

Useful URLs:

- API docs: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`
- Health check: `http://localhost:8000/api/v1/health/`

## Demo API collection

A demo-ready Bruno collection lives at:

```text
bruno/placamia-api
```

Open that directory in Bruno and select the `Local` environment after starting
the backend with `make dev`. The collection includes health, catalog categories,
catalog products, catalog product detail, catalog kits, and current-user
requests.

See `docs/api/bruno.md` for details.

## Run tests

```bash
make test
```

The current test suite runs locally without PostgreSQL. Tests use in-memory
SQLite databases or dependency overrides where appropriate.

## Developer commands

| Command | Purpose |
| --- | --- |
| `make dev` | Start the FastAPI backend with reload. |
| `make test` | Run the backend pytest suite. |
| `make migrate` | Apply Alembic migrations to the configured database. |
| `make migration m="message"` | Generate an Alembic migration with autogenerate. |
| `make downgrade` | Roll back one Alembic migration. |
| `make seed` | Seed local catalog data. |

## Environment configuration

Backend settings are read from environment variables. During local development,
`apps/api/app/core/config.py` loads `apps/api/.env`.

Required local values are documented in `apps/api/.env.example`:

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | FastAPI application title. |
| `ENV` | Environment label such as `local`, `test`, or `production`. |
| `DATABASE_URL` | SQLAlchemy database connection URL. |
| `SQLALCHEMY_ECHO` | Enables SQL logging when set to a truthy value. Keep `false` by default. |
| `AUTH_TOKEN_SECRET` | Secret used to sign and verify backend access tokens. |

The split `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` values
in `.env.example` mirror the local Docker database and are kept for developer
clarity. Runtime database connections currently use `DATABASE_URL`.

See `docs/architecture/environment-strategy.md` for environment rules.

## Contribution rules

- Work from a GitHub issue
- Create a feature branch from `main`
- Keep PRs scoped to one issue
- Add or update tests for every behavior change
- Use Alembic for schema changes
- Update docs when behavior or workflow changes
- Follow `AGENTS.md` for implementation rules

## Pull request expectations

Each PR must include:
- linked issue
- concise summary
- acceptance criteria covered
- tests added/updated
- docs or migration notes when applicable
