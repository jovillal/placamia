# Admin / Backoffice

## Goal

Define the administrative surface needed to manage PlacamIA safely without
mixing customer-facing catalog behavior with privileged mutations.

Admin/backoffice work must build on the existing authentication, authorization,
and audit logging foundation.

## Scope

- Admin endpoint grouping and authorization requirements
- Admin-only product, kit, price, order, supplier, and user workflows
- Audit logging for security-relevant admin actions
- Current-user and role handling for protected admin routes

## Related Docs

- `docs/planning/security.md`
- `docs/architecture/security.md`
- `docs/api/endpoint-structure.md`
- `docs/api/api-style.md`

## Endpoints

Planned:

- `/api/v1/admin/...`

Specific admin paths must be defined by future scoped issues before
implementation.

## Child Issues

Open, but needs issue-template cleanup before implementation:

- #68 Define admin endpoints
- #71 Authentication/current-user
- #72 Authorization/audit logging

## Constraints

- Admin endpoints must require admin authorization.
- Admin mutations must be auditable when they affect products, kits, prices,
  discounts, orders, supplier integration, or users.
- Do not introduce a full RBAC system unless a planning document and issue
  explicitly define it.
- Do not expose admin behavior through customer-facing catalog endpoints.

## Security Considerations

- Never trust frontend-provided `role`, `is_admin`, or ownership claims.
- Derive the current user from the authenticated request.
- Do not log secrets, tokens, full payment data, or sensitive payloads.
- Rejected admin requests must not mutate database state.

## Done When

- Admin endpoint groups are defined.
- Admin authorization behavior is documented and implemented.
- Admin mutations are covered by audit logging.
- Non-admin access is rejected and tested.
- Admin behavior appears correctly in FastAPI docs.
