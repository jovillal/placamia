# Existing Backend Security Review

## Purpose

This note records the issue #46 review of existing backend work against the
security rules in `AGENTS.md`, `docs/architecture/security.md`, and the pull
request template.

## Review Date

2026-04-28

## Current Backend Surface

- Public health endpoint: `GET /api/v1/health/`
- Public catalog categories endpoint: `GET /api/v1/catalog/categories`
- SQLAlchemy models for users, categories, and products
- Repository and service layers for categories and products
- Catalog seed script for local development and test data
- Alembic migrations for current schema

No authentication, authorization, admin endpoints, checkout endpoints, payment
webhooks, order endpoints, or user-specific API endpoints exist yet.

## Acceptance Criteria Review

### Secrets and Environment Files

No `.env` files are tracked. The repository tracks `.env.example` and
`apps/api/.env.example` only. Real `.env` files remain ignored by `.gitignore`.

`apps/api/.env.example` contains local development placeholder values only and
does not include production credentials.

### API Input Validation

The current public API endpoints do not accept request bodies or write data.
Responses are constrained through explicit response schemas.

Future request-body endpoints must use strict Pydantic schemas and reject
unknown or invalid fields where practical.

### Authentication and Authorization

The current endpoints are public health and catalog-read endpoints. There are no
protected, user-specific, or admin endpoints to enforce yet.

Before adding user-specific resources, the backend must introduce authenticated
current-user resolution and ownership checks.

### Frontend Ownership Claims

No current endpoint accepts `user_id`, `role`, `is_admin`, or other ownership
claims from the frontend.

### Pricing and Order Integrity

Products include `base_price` seed data, but there is no quote, checkout,
payment, or order creation flow yet.

Future pricing and order endpoints must calculate totals server-side and ignore
frontend-supplied totals.

### Admin Behavior

No admin API behavior exists yet. Future admin endpoints must require explicit
admin authorization and log security-relevant changes.

### Sensitive Logging

SQLAlchemy query echo is disabled by default through `SQLALCHEMY_ECHO=false`.
Developers may opt in locally, but production should keep query echo disabled to
avoid logging sensitive values.

The existing AI PR review helper reports missing environment variable names but
does not print secret values.

## Remediation Completed

- Disabled SQLAlchemy query echo by default.
- Added `SQLALCHEMY_ECHO=false` to `apps/api/.env.example`.
- Added tests that assert SQL logging remains opt-in.

## Follow-Up Gaps

Create separate issues before implementing these larger security capabilities:

- Add authentication and current-user dependency before introducing protected
  user-specific endpoints.
- Add authorization and audit logging before introducing admin endpoints.
- Add server-side quote and checkout pricing tests before implementing checkout
  or order creation.
- Define inactive product behavior before exposing product listing endpoints to
  customers or allowing products to be ordered.
- Add payment webhook signature verification tests before integrating a payment
  provider.
