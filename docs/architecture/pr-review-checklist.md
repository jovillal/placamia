# PlacamIA PR Review Checklist

## 1. Scope
- [ ] The PR matches the GitHub issue
- [ ] No unrelated features were added
- [ ] No silent architecture changes were introduced
- [ ] The PR links one primary GitHub issue
- [ ] The PR stays scoped to that issue
- [ ] The branch name is reasonably descriptive

## 2. Structure
- [ ] Files were added in the correct locations
- [ ] Models are in `apps/api/app/models`
- [ ] Schemas are in `apps/api/app/schemas`
- [ ] Repositories are in `apps/api/app/repositories`
- [ ] Services are in `apps/api/app/services`
- [ ] Endpoints are in `apps/api/app/api/v1/endpoints`

## 3. Architecture
- [ ] Route handlers are thin
- [ ] Business logic is in services, not routes
- [ ] Repositories only handle data access
- [ ] The modular monolith structure is preserved
- [ ] No unnecessary abstractions were introduced

## 4. Database and migrations
- [ ] Schema changes use Alembic
- [ ] Migration only contains intended changes
- [ ] Migration names are clear
- [ ] No accidental table or column changes slipped in
- [ ] Models and migrations match each other

## 5. API quality
- [ ] Endpoints follow `/api/v1`
- [ ] Resource names are consistent
- [ ] Request validation uses Pydantic schemas
- [ ] Responses are consistent with the API style guide
- [ ] Errors are meaningful and do not leak internals

## 6. Testing
- [ ] Tests were added or updated
- [ ] Unit tests exist for service/repository logic where appropriate
- [ ] Integration tests exist for new endpoints
- [ ] `make test` passes
- [ ] Tests actually cover the implemented behavior

## 7. Code quality
- [ ] Names are clear and explicit
- [ ] Functions are reasonably small
- [ ] Code is readable without mental gymnastics
- [ ] No dead code or commented-out junk remains
- [ ] No hardcoded secrets or environment-specific values were added

## 8. MVP discipline
- [ ] The PR stays inside MVP scope
- [ ] No AI features were introduced unless explicitly requested
- [ ] No infra complexity was introduced
- [ ] No speculative future-proofing bloated the implementation

## 9. Documentation
- [ ] Docs were updated if behavior or structure changed
- [ ] AGENTS.md rules were followed
- [ ] Any new command or workflow is documented

## 10. Final sanity
- [ ] The feature works locally
- [ ] The PR can be explained simply
- [ ] I would be comfortable merging this into `main`