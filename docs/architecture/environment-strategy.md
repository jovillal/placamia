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

The local PostgreSQL container publishes port `54322` on the host and keeps
PostgreSQL's internal container port at `5432`. The project-specific host port
avoids collisions with other local PostgreSQL projects that use the standard
default port.

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

### Migration Preflight Notes

Before applying migrations to any populated environment, run data-shape checks
for constraints that may fail on legacy rows. For the payments uniqueness
constraint on non-null `(order_id, payment_provider_reference)` pairs, verify
there are no duplicates before running Alembic:

```sql
SELECT
    order_id,
    payment_provider_reference,
    COUNT(*) AS duplicate_count
FROM payments
WHERE payment_provider_reference IS NOT NULL
GROUP BY order_id, payment_provider_reference
HAVING COUNT(*) > 1;
```

If this query returns rows, stop the migration and resolve the duplicate
payment history through a scoped data-cleanup issue or runbook before applying
the constraint. Do not delete or merge payment rows ad hoc during deploy.

The Wompi provider-identity rollout uses separate expand and contract
migrations:

1. The expand migration adds nullable `provider_code` and
   `merchant_reference`, creates provider transaction/event tables, and
   backfills every existing Payment as `legacy_generic` with
   `legacy-payment-{payment_id}` merchant identity.
2. Existing `payment_provider_reference` and generic webhook replay rows remain
   unchanged. The migration must not invent Wompi transaction/event rows from
   generic history.
3. After the expand migration, run these preflight checks before applying the
   non-null/unique contract migration:

```sql
SELECT id
FROM payments
WHERE provider_code IS NULL
   OR merchant_reference IS NULL;

SELECT
    provider_code,
    merchant_reference,
    COUNT(*) AS duplicate_count
FROM payments
GROUP BY provider_code, merchant_reference
HAVING COUNT(*) > 1;
```

Both queries must return no rows. The contract migration may then make both
columns non-null and add unique `(provider_code, merchant_reference)`. Enable
`PAYMENT_PROVIDER_DEFAULT=wompi` only after that migration and Wompi runtime
configuration are ready.

`legacy_generic` is historical/read-only identity. Active generic Payments are
not routed to Wompi and require an explicit operational closure decision before
a new Wompi Payment is created. Existing verified Orders retain their original
payment reference and verification timestamp.

## Environment Variables

| Variable | Required Locally | Purpose |
| --- | --- | --- |
| `APP_NAME` | Yes | FastAPI application title. |
| `ENV` | Yes | Environment label. |
| `DATABASE_URL` | Yes for local runtime | SQLAlchemy connection URL. |
| `SQLALCHEMY_ECHO` | Yes | SQL logging flag; defaults should remain `false`. |
| `AUTH_TOKEN_SECRET` | Yes for protected endpoints | Token signing and verification secret. |
| `PAYMENT_WEBHOOK_SECRET` | Yes for the current generic webhook foundation | Local/test HMAC secret; it is not a Wompi production event secret. |

`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` are documented in
`apps/api/.env.example` to mirror the local PostgreSQL container. The runtime
connection currently uses `DATABASE_URL`.

### Planned Wompi Configuration

The Wompi production boundary is approved in ADR 0004 but is not implemented.
The variables below become active only with the provider-specific implementation
and must be added to `apps/api/.env.example` in that code change with safe local
placeholders, never real credentials.

| Variable | Secret | Purpose |
| --- | --- | --- |
| `PAYMENT_PROVIDER_DEFAULT` | No | Provider code selected only for newly created Payments; initial value `wompi`. |
| `PAYMENT_RETURN_URL` | No | Approved absolute PlacamIA URL used for customer navigation after hosted checkout. |
| `PAYMENT_CHECKOUT_TTL_SECONDS` | No | Backend-owned checkout-start window; initial default `1800` seconds. |
| `WOMPI_ENVIRONMENT` | No | Explicit `sandbox` or `production` adapter mode. |
| `WOMPI_PUBLIC_KEY` | No, but runtime-managed | Public commerce key used by Wompi Web Checkout. |
| `WOMPI_INTEGRITY_SECRET` | Yes | Backend-only secret used to sign checkout integrity values. |
| `WOMPI_EVENT_SECRET` | Yes | Backend-only secret used to verify Wompi event checksums. |

The adapter maps `WOMPI_ENVIRONMENT` to allowlisted Wompi API and checkout
hosts. Do not accept an arbitrary provider base URL in production configuration.
`PAYMENT_RETURN_URL` must use HTTPS outside local/test environments and must be
validated against an application-owned allowlist.

Changing `PAYMENT_PROVIDER_DEFAULT` affects only new Payments. Existing
Payments resolve their adapter from persisted `provider_code`, so old Wompi
webhooks and reconciliation remain valid after a gradual provider migration.

Provider secrets must fail closed when missing. They must not appear in startup
logs, error responses, audit payloads, or generated checkout URLs. The current
`PAYMENT_WEBHOOK_SECRET` remains only for the generic implemented foundation
until provider-specific routes replace it; it must not be reused as either
Wompi secret.

## Command Summary

| Command | Environment | Purpose |
| --- | --- | --- |
| `make dev` | local | Start the FastAPI backend. |
| `make test` | test | Run pytest locally without external services. |
| `make migrate` | local | Apply Alembic migrations to the configured database. |
| `make migration m="message"` | local | Generate a migration with Alembic autogenerate. |
| `make seed` | local | Seed catalog data for development. |
