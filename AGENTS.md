# PlacamIA — Codex Instructions

## Project Overview
PlacamIA is a mobile-first application that allows users to design, quote, and purchase industrial safety signage.

The MVP focuses on:
- catalog (products + kits)
- rules-based customization (NOT AI)
- pricing
- checkout
- order tracking

AI features are explicitly out of scope for MVP.

---

## Tech Stack

- Backend: FastAPI (Python)
- Database: PostgreSQL
- ORM: SQLAlchemy
- Migrations: Alembic
- Testing: pytest

---

## Project Structure

- apps/api → FastAPI backend
- apps/mobile → future mobile app
- docs → architecture + product docs
- scripts → dev scripts

Inside backend:

- app/models → SQLAlchemy models
- app/schemas → Pydantic schemas
- app/repositories → DB access
- app/services → business logic
- app/api/v1/endpoints → routes

---

## How to Run

```bash
make dev
```

## How to Run Tests
```bash
make test
```

## How to Run Migrations
```bash
make migrate
make migration m="message"
```
---

## Responsibilities

Codex acts as:

### 1. Backend Developer
- implement models, services, endpoints

### 2. Test Engineer
- add unit tests for business logic
- add integration tests for endpoints
- ensure tests pass before completion

### 3. Documentation Writer
- add docstrings to all new code
- ensure endpoints are documented via FastAPI
- keep code self-explanatory

All three responsibilities must be fulfilled for every task.

---

## Core Architectural Rules
- Keep a modular monolith
- Do NOT introduce microservices
- Do NOT introduce new frameworks
- Prefer simple, explicit code over abstractions
- Keep logic readable and debuggable

---

## Domain Rules
Important concepts:

 - Product = sellable item
 - Template = design base
 - Design = customized instance of a template
 - Kit = bundle of products

Templates and Designs are separate entities.

---

## MVP Scope Rules

IN SCOPE:

 - catalog
 - kits
 - pricing
 - checkout
 - order tracking

OUT OF SCOPE:

 - AI generation
 - 3D rendering
 - AR
 - gamified credit systems
 - collaborative projects

---

## Testing Rules (MANDATORY)

When modifying or adding functionality:

 - ALWAYS add or update tests
 - Prefer unit tests for services and business logic
 - Add integration tests for API endpoints
 - Do NOT mark work complete without tests
 - Follow `docs/architecture/testing.md` for test structure, fixture conventions, and authentication testing patterns

 ---

## Definition of Done

A task is complete only if:

 - code runs without errors
 - tests pass
 - migrations work (if DB changed)
 - API endpoints are functional (if added)
 - docstrings are included
 - API endpoints appear correctly in /docs
 - no unnecessary complexity introduced

 ---

## Coding Guidelines
 - Use clear naming (no abbreviations)
 - Keep functions small and focused
 - Avoid premature abstractions
 - Prefer explicit logic over “magic”
 - Keep business logic in services, not routes

---

## Security Rules

Security is mandatory for every implementation.

Before writing or modifying code, check whether the change affects:

- authentication
- authorization
- pricing
- checkout
- payments
- orders
- user data
- supplier integration
- file/image handling
- admin behavior
- environment variables or secrets

If yes, the implementation must include security validation and tests.

### Mandatory Security Requirements

- Never hardcode secrets, credentials, tokens, or API keys.
- Never commit `.env` files.
- Never trust frontend-calculated prices.
- Never trust frontend ownership claims such as `user_id`, `role`, or `is_admin`.
- Never expose another user's data.
- Never create admin behavior without explicit authorization checks.
- Never store payment card data.
- Never log passwords, tokens, secrets, or full payment data.
- Validate all API input with explicit schemas.
- Use backend-side authorization checks on protected endpoints.
- Use Alembic for database schema changes.
- Add or update tests for security-relevant behavior.

### Pricing and Checkout Rules

The backend is the source of truth for all pricing.

The frontend may request a quote using product, material, size, quantity, and kit selections, but the backend must calculate the final amount.

Order creation must use backend-calculated prices only.

Any implementation involving checkout must consider:

- price tampering
- invalid product options
- inactive products
- quantity abuse
- payment confirmation spoofing

### Authorization Rules

Protected endpoints must derive the current user from the authenticated request.

Do not accept `user_id`, `role`, or ownership fields from the frontend as proof of authorization.

Users may only access their own resources unless the endpoint is explicitly admin-only.

### Admin Rules

Admin endpoints must require admin authorization.

Admin changes must be logged when they affect:

- products
- kits
- prices
- discounts
- orders
- supplier integration
- users

### File Handling Rules

Uploaded or generated files must be validated.

Check:

- file type
- file size
- extension
- storage destination

S3 buckets must not be public by default.

### Logging Rules

Logs should support debugging and incident investigation, but must not leak sensitive data.

Do not log:

- passwords
- JWTs
- refresh tokens
- payment card data
- secrets
- full environment variables

### Security Test Expectations

When applicable, add tests for:

- unauthenticated access rejected
- unauthorized access rejected
- user cannot access another user's resources
- non-admin cannot perform admin actions
- frontend-supplied price is ignored
- invalid inputs are rejected
- invalid payment webhook signatures are rejected

---

## Migration Rules
 - Always use Alembic for schema changes
 - Always generate migrations with autogenerate
 - Review migrations before applying

---

## When implementing a task from GitHub issues:
- Treat the GitHub issue acceptance criteria as the source of truth
- In the pull request description, explicitly list which acceptance criteria were implemented
- If any acceptance criterion was not implemented, state it clearly
- If the issue lacks acceptance criteria, do not guess silently; keep implementation minimal and document assumptions in the PR

Examples of silent changes that must be called out in the PR:
- schema or migration changes
- renamed endpoints or response shapes
- new environment variables
- dependency additions
- changes to architectural boundaries
- behavior changes outside the issue scope

---

## Documentation Rules

When adding or modifying code:

- Always include docstrings for:
  - models
  - services
  - repositories
  - endpoints

- Docstrings must explain:
  - purpose of the function/class
  - inputs
  - outputs
  - side effects (if any)

- For each new endpoint:
  - include a clear description
  - define request/response structure
  - use FastAPI's built-in documentation features

- For each CRUD resource:
  - ensure it is discoverable via FastAPI docs (/docs)

## Git Workflow Rules

When working on a task:

- Always read the corresponding GitHub issue first
- Create a new branch from main:
  - format: feature/<short-description>
- Do NOT commit directly to main
- Make small, clear commits
- Use descriptive commit messages (feat:, fix:, test:, etc.)
- Keep changes scoped to the issue

## Pull Request Rules

All work should be reviewable through a focused pull request.

Before considering a task complete:
- ensure the branch is scoped to one issue
- ensure tests were added or updated
- ensure migrations were reviewed if schema changed
- ensure the PR can be explained in a short summary

Each PR description must contain:

- Linked issue
- Summary of change
- Acceptance criteria covered
- Tests added/updated
- Migrations/config changes
- Documentation updates
- Out-of-scope items intentionally not included
- State any assumptions made due to ambiguity in the issue
- State any related work intentionally left out of scope

## Issue quality requirements

Implementation issues should include:
- problem statement
- scope
- acceptance criteria
- out-of-scope notes when relevant

If these are missing, do not silently expand scope.

## What NOT to do
 - Do not introduce AI features unless explicitly requested
 - Do not redesign architecture
 - Do not add infra complexity (no Kubernetes, no Terraform)
 - Do not guess domain behavior — follow docs

---

## When in doubt

 - prefer simplicity
 - prefer readability
 - prefer MVP constraints
