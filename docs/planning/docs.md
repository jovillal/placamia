# Docs

## Goal

Keep project documentation aligned with implemented behavior, planning
milestones, database shape, and MVP constraints.

Docs are not the product behavior source of truth by themselves; they preserve
and communicate decisions made in planning documents, flow docs, architecture
docs, and accepted implementation issues.

## Scope

- Architecture diagrams and database diagrams
- Planning document maintenance
- Flow document maintenance
- API documentation examples and inventories
- Product and MVP scope documentation

## Related Docs

- `docs/flows/main-flow.md`
- `docs/api/endpoint-structure.md`
- `docs/api/api-style.md`
- `docs/architecture/database-diagram.dbml`

## Child Issues

Open:

- #38 Database diagram

## Future Issues

- Future issue required: reconcile duplicate MVP scope documentation issues if
  more duplicate docs issues are created.
- Future issue required: define when generated diagrams should be refreshed from
  source docs.

## Constraints

- Do not change system behavior through docs-only work.
- Do not treat manual diagrams as authoritative over Mermaid flow docs.
- Keep database diagrams aligned with Alembic migrations and SQLAlchemy models.
- Keep docs scoped to MVP unless a planning document explicitly marks work as
  post-MVP.

## Done When

- Database diagram reflects implemented schema.
- Planning docs reflect current milestones and known future issues.
- API docs reflect implemented endpoints and response shapes.
- Documentation avoids stale MVP contradictions.
