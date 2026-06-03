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
 - Follow `docs/architecture/testing.md` for test structure, fixture conventions, authentication testing patterns, and security-sensitive rejection test expectations
 - Tests should align with system flows defined in `docs/flows/*.md`, especially for security-sensitive paths such as checkout and payment confirmation.

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
- provider integration
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
- provider integration
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
- checkout and order creation reject tampered or invalid inputs without creating records
- invalid payment webhook signatures are rejected
- rejected security-sensitive requests do not mutate database state or trigger external side effects

---

## Source of Truth Hierarchy

PlacamIA uses a layered source of truth model.

### 1. Planning Documents (Primary)

Located under:

- `docs/flows/*.md`
- `docs/planning/*.md`

These define:

- system behavior (flows)
- domain concepts
- feature scope
- constraints
- security expectations

All implementation must follow these documents.

### 2. GitHub Issues (Execution Layer)

Issues represent executable work derived from planning documents.

Each issue must:

- reference a planning document
- include clear acceptance criteria
- remain scoped to a single concern

Issues must not redefine system behavior.

### 3. Mermaid Diagrams (Derived)

Mermaid diagrams inside `docs/flows/*.md` are the canonical visual representation of system behavior.

Manual diagrams (e.g. diagrams.net) are optional and must not be treated as authoritative.

---

## Migration Rules
 - Always use Alembic for schema changes
 - Always generate migrations with autogenerate
 - Review migrations before applying

---

## Implementation Rules (Updated)

Before implementing any issue:

1. Read the referenced planning document
2. Review `docs/flows/main-flow.md`
3. Ensure implementation aligns with defined flow and constraints

If discrepancies are found:

- do not guess
- do not silently adjust behavior
- update planning docs or raise a question in the issue

---

### When implementing a task from GitHub issues:
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

Any change that affects:

- system flow
- domain behavior
- API contracts

must update:

- relevant planning document
- and/or `docs/flows/main-flow.md`

---

## Git Workflow Rules

When working on a task:

- Always read the corresponding GitHub issue first
- Create a new branch from main:
  - format: feature/<short-description>
- Do NOT commit directly to main
- Make small, clear commits
- Use descriptive commit messages (feat:, fix:, test:, etc.)
- Keep changes scoped to the issue

---

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

---

## Issue quality requirements

Implementation issues should include:
- problem statement
- scope
- acceptance criteria
- out-of-scope notes when relevant

If these are missing, do not silently expand scope.

---

## What NOT to do
 - Do not introduce AI features unless explicitly requested
 - Do not redesign architecture
 - Do not add infra complexity (no Kubernetes, no Terraform)
 - Do not guess domain behavior — follow docs

---

## Prohibited Behaviors

- Implementing features not defined in planning documents
- Treating GitHub issues as the source of truth for system design
- Bypassing backend validation rules defined in planning docs
- Introducing flow changes without updating Mermaid diagrams

---

## When in doubt

 - prefer simplicity
 - prefer readability
 - prefer MVP constraints

---

## Codex Execution Protocol (Strict Mode)

Codex must follow this protocol for every implementation task.

### 1. Pre-Implementation Checklist (MANDATORY)

Before writing any code, Codex must verify:

- A planning document is referenced
- The flow in `docs/flows/main-flow.md` is understood
- The issue contains acceptance criteria

If any of these are missing or unclear:

- STOP
- Do not implement blindly
- Document assumptions in the PR

---

### 2. Scope Control

Codex must:

- implement ONLY what is explicitly required
- NOT expand scope based on assumptions
- NOT introduce new behavior without documentation updates

If a required dependency is missing:

- implement the minimum needed
- clearly state the limitation in the PR

---

### 3. Deterministic Behavior

Codex must ensure:

- all business logic is deterministic
- no hidden or implicit behavior is introduced
- all decisions are traceable to:
  - planning docs
  - issue acceptance criteria

---

### 4. Validation Before Completion

Before marking a task as complete, Codex must verify:

- tests exist and pass
- API behavior matches expected contract
- no security rules were violated
- no flow contradictions exist with Mermaid diagrams

---

### 5. Mandatory PR Self-Review

Before submitting a PR, Codex must internally validate:

- Did I deviate from the planning document?
- Did I introduce behavior not explicitly defined?
- Did I skip any acceptance criteria?
- Did I update docs if behavior changed?

If any answer is "yes":

- explicitly document it in the PR

---

### 6. Stop Conditions (CRITICAL)

Codex must STOP and NOT proceed if:

- domain behavior is ambiguous
- planning docs contradict each other
- issue scope is unclear or incomplete
- required security behavior is undefined

In these cases:

- implement minimal safe behavior OR
- document assumptions clearly in the PR

Never silently guess.

---

### 7. Output Expectations

All implementations must produce:

- working code
- passing tests
- updated documentation (if needed)
- clear PR description with:
  - acceptance criteria coverage
  - assumptions
  - limitations
