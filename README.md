# PlacamIA

PlacamIA is a mobile-first application that allows users to design, quote, and purchase industrial safety signage using templates and rules-based customization.

## Current phase
Initial setup:
- repository structure
- backend foundation
- local PostgreSQL
- migrations
- documentation
- GitHub project setup

AI-assisted generation is out of scope for the MVP.

## Monorepo structure

```text
apps/
  api/        FastAPI backend
  mobile/     Future mobile application
docs/
  architecture/
  product/
  api/
infra/
scripts/
.github/
```

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
