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
