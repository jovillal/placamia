# Foundation

## Goal

Establish the technical and architectural baseline for PlacamIA.

This includes project structure, development workflow, database setup,
testing architecture, and core conventions.

Foundation must ensure that all future features can be built safely,
tested properly, and maintained over time.

## Scope

- Repository structure
- Backend framework setup (FastAPI)
- Database configuration (PostgreSQL)
- ORM and migrations (SQLAlchemy + Alembic)
- Development environment
- Testing architecture
- API structure conventions
- Documentation baseline

## Related Docs

- `AGENTS.md` — Codex/project execution rules
- `README.md` — repository overview, current phase, contribution rules
- `docs/architecture/testing.md` — testing architecture and security-sensitive test expectations
- `docs/architecture/security.md` — security baseline and mandatory security rules
- `docs/architecture/environment-strategy.md` — local/test/prod environment strategy
- `docs/api/endpoint-structure.md` — API groups and implemented endpoint inventory
- `docs/api/api-style.md` — API naming, request, response, and error conventions
- `docs/architecture/database-diagram.dbml` — database diagram source

## Key Decisions

- Modular monolith architecture
- No microservices
- Backend owns all business logic
- Tests are mandatory for all features
- Security is enforced from the start

## Environment Strategy

- local-first development
- same codebase across environments
- configuration via environment variables

## API and Documentation Baseline

- API endpoints must use the `/api/v1` prefix.
- API responses must follow the project API style guide.
- New or changed API behavior must be reflected in the relevant docs.
- Planning docs and flow docs are the primary source of truth for implementation.

## Implemented Components

- Project structure initialized
- FastAPI application created
- PostgreSQL database configured
- Alembic migrations working
- Base models (User, Category, Product)
- Health endpoint implemented
- Basic catalog endpoint implemented

## Child Issues

- #11 finalize backend baseline and developer commands
- #13 standardize API style and endpoint structure docs
- #38 Database diagram
- #50 Add authorization and audit logging foundation
- #59 document security-focused testing architecture

## Constraints

- Keep architecture simple
- Avoid premature abstractions
- Follow AGENTS.md rules strictly
- All changes must include tests

## Security Considerations

- No secrets in code
- Backend must enforce all validation
- Authentication required before protected endpoints
- Pricing and order integrity must be server-side

## Done When

- Developers can run the project locally
- Database migrations work reliably
- API structure is consistent
- Testing framework is operational
- Security baseline is defined and documented
