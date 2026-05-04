# Security

## Goal

Keep PlacamIA secure as MVP capabilities expand into pricing, checkout,
orders, payments, admin behavior, and provider handoff.

Security planning turns the architecture baseline into executable hardening and
test-coverage work.

## Scope

- Authentication and current-user behavior
- Authorization boundaries
- Audit logging and redaction
- Security-critical test coverage
- Payment webhook verification test foundation
- Inactive product behavior across catalog and ordering
- Server-side quote and checkout pricing test foundation

## Related Docs

- `docs/architecture/security.md`
- `docs/architecture/testing.md`
- `docs/architecture/security-review-existing-backend.md`
- `docs/flows/main-flow.md`
- `docs/flows/checkout-flow.md`

## Core Principles

- Never trust frontend ownership claims.
- Never trust frontend-calculated prices.
- Never expose another user's data.
- Never log secrets, tokens, full payment data, or sensitive payloads.
- Rejected security-sensitive requests must not mutate database state.

## Implemented Foundation

- #45 Add security architecture and secure coding rules
- #46 Review backend against new security rules
- #49 Add authentication and current-user dependency for protected endpoints
- #50 Add authorization and audit logging foundation for admin endpoints
- #59 Document security-focused testing architecture

## Child Issues

Planned:

- #51 Add server-side quote and checkout pricing test foundation
- #52 Define inactive product behavior for customer catalog and ordering
- #53 Add payment webhook signature verification test foundation
- #58 Enforce security-critical test coverage
- #67 Harden audit logging redaction and role handling

Needs issue-template cleanup before implementation:

- #69 Security architecture
- #70 Backend security review
- #73 Security-critical testing
- #74 Security-focused testing architecture

## Future Issues

- Future issue required: define authorization matrix for user-owned resources
- Future issue required: define payment webhook replay/idempotency behavior
- Future issue required: define audit event retention expectations
- Future issue required: define admin action audit event coverage

## Constraints

- Do not introduce a full RBAC system unless a planning document and issue
  explicitly define it.
- Do not add payment, checkout, order, provider, or admin behavior from a
  security-hardening issue unless that behavior is explicitly scoped.
- Keep security tests focused on actual risk and documented system flows.

## Done When

- Security-critical paths have explicit rejection tests.
- Audit logs redact sensitive keys and values according to documented policy.
- Role handling is documented and tested at the chosen level of strictness.
- Pricing, checkout, payment, order, and admin issues include security test
  expectations before implementation.
- Security planning stays aligned with architecture and testing docs.
