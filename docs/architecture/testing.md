# Testing Architecture

## Purpose

This document defines how PlacamIA tests backend behavior as authentication,
authorization, pricing, checkout, orders, and admin workflows are added.

The goal is to keep security meaningful without making every integration test
slow or hard to read.

This document is the testing source of truth for security-sensitive feature
work. It must stay consistent with `docs/architecture/security.md`,
`docs/flows/main-flow.md`, and security-critical flow documents such as
`docs/flows/checkout-flow.md`.

## Principles

- Test business rules at the service layer first.
- Test API wiring with focused integration tests.
- Test security-sensitive rejected behavior as explicitly as accepted behavior.
- Keep authentication parsing behind reusable dependencies.
- Override dependencies in most endpoint tests instead of creating real tokens
  for every request.
- Use real authentication validation only where the authentication path itself
  is under test.
- Critical business invariants (pricing, orders, payments) must be tested explicitly.

## Test Boundaries

### Unit and Service Tests

Use unit or service tests for deterministic business behavior that does not
need HTTP, FastAPI routing, or token parsing.

Examples:

- pricing calculations
- invalid product options
- inactive product rejection
- ownership checks
- admin permission checks
- audit log creation
- webhook signature verification helpers

Service tests should receive explicit inputs, such as a user object or user id,
instead of depending on FastAPI request state. They should assert the direct
business outcome and, for rejected security-sensitive actions, assert that no
database mutation or external side effect occurred.

### API Integration Tests

Use API integration tests for route behavior, dependency wiring,
request/response contracts, and database-visible API outcomes.

Examples:

- unauthenticated requests are rejected
- unauthorized users receive the correct error
- request schemas reject invalid input
- endpoints return documented response shapes
- dependency wiring resolves the current user correctly

Endpoint tests may override `get_current_user` or similar dependencies when the
test is not specifically about token parsing. API integration tests should still
exercise the real route, schema validation, repository/database behavior, and
error response shape.

### Full Authentication Path Tests

Use full authentication-path tests for real authentication parsing, token
validation, and current-user resolution. These tests should cover the reusable
authentication dependency itself and a small representative set of protected
endpoints.

Examples:

- missing authorization headers are rejected
- malformed credentials are rejected
- expired or invalid tokens are rejected
- valid credentials resolve the expected current user
- inactive or missing users referenced by otherwise valid credentials are rejected

Do not require every endpoint test to mint or verify real tokens.

## Authentication Testing Pattern

Authentication should be exposed to endpoints through one reusable dependency,
such as `get_current_user`.

Most endpoint tests should use FastAPI dependency overrides:

```python
async def override_get_current_user():
    return test_user


app.dependency_overrides[get_current_user] = override_get_current_user
```

Use this pattern when the test is about endpoint behavior after authentication
has already succeeded. Good examples include ownership checks, request schema
validation, order state transitions, pricing tamper rejection, and admin-only
authorization behavior.

Do not use this shortcut when the test is about:

- missing credentials
- invalid credentials
- token verification
- current-user lookup failure
- protected endpoints rejecting unauthenticated requests
- authentication headers or token payload formats

When a dependency override is used, the test must not claim to verify real
authentication. Name the test and fixtures so the boundary is clear.

## Fixture Conventions

Prefer clear fixture names that describe the security posture:

- `test_user`
- `admin_user`
- `other_user`
- `authenticated_client`
- `admin_client`
- `auth_headers`
- `admin_auth_headers`

Fixtures should avoid hardcoded production-like secrets. Test-only secrets may
be defined in test configuration or monkeypatched environment variables.

## Test Function Docstrings

Descriptive backend test function names are sufficient by default. New and
materially modified tests do not need docstrings when the behavior is clear
from the test name, fixtures, and assertions.

Use a test docstring when it explains context that would otherwise be easy to
miss, such as:

- security-sensitive behavior or threat boundaries
- non-obvious lifecycle, state-machine, or transaction invariants
- complex setup that is not apparent from fixture names
- regression scenarios where the historical failure is important context
- why a documentation-only or policy-only test choice intentionally has no
  runtime assertion changes

This rule is prospective. Existing tests do not need repository-wide docstring
cleanup solely to match this guidance.

## Security Test Expectations

When applicable, add tests for:

- unauthenticated access rejected
- unauthorized access rejected
- user cannot access another user's resources
- non-admin cannot perform admin actions
- frontend-supplied price is ignored
- invalid inputs are rejected
- inactive products cannot be ordered
- invalid payment webhook signatures are rejected

Security-sensitive tests must verify that rejected requests do not mutate
database state or trigger external side effects.

Required rejection coverage by area:

| Area | Required rejection tests |
| --- | --- |
| Authentication | Missing, malformed, expired, invalid, or unresolvable credentials are rejected. |
| Authorization | Users cannot access or mutate resources they do not own. |
| Pricing | Frontend-supplied price, subtotal, discount, tax, or total is ignored or rejected. |
| Checkout | Invalid product options, inactive products, invalid quantities, and price tampering do not create orders or payment attempts. |
| Orders | Unauthorized order reads or updates are rejected and do not reveal another user's data. |
| Payments | Missing, invalid, spoofed, or replayed payment confirmations do not mark orders as paid. |
| Admin behavior | Non-admin users cannot perform admin actions, and accepted admin mutations are auditable. |

Security-sensitive areas include pricing, order creation, payment confirmation,
and provider handoff. Treat changes in those areas as security-relevant even
when the endpoint or service appears operational rather than authentication
focused.

## Pull Request Expectations

Every implementation PR should explain:

- which service tests were added or updated
- which API integration tests were added or updated
- which security rejection paths are covered
- why tests were not added, if the change is documentation-only

Documentation-only PRs do not need runtime tests, but should still be reviewed
for consistency with `AGENTS.md`, `docs/architecture/security.md`, and the
issue acceptance criteria.

## Critical Business Security Tests

The following test categories are mandatory for PlacamIA due to the nature of
pricing, checkout, and provider fulfillment.

### Pricing Integrity

- Backend ignores any frontend-supplied price, subtotal, discount, or total.
- Pricing is recalculated based only on:
  - product id
  - material
  - size
  - quantity
  - kit composition
- Modified or inconsistent pricing inputs are rejected or ignored.
- Price mismatches are logged without sensitive data or full request payloads.

### Order Integrity

- Orders cannot be created with:
  - inactive products
  - invalid combinations of product/material/size
  - manipulated quantities outside allowed ranges
- Orders must be created only from validated backend state.
- Repeated order submissions (same payload) do not create duplicate orders
  unless explicitly allowed.

### Payment Integrity

- Payment webhook or confirmation endpoints:
  - reject invalid provider-specific signatures or checksums
  - reject missing signatures
  - return HTTP 200 `already_processed` for authenticated matching duplicates
    whose original transaction committed
  - reject a reused replay reference with a different payload hash
- Payment initialization tests verify that provider selection, amount,
  currency, merchant reference, expiration, and signature inputs come only from
  backend-owned state.
- Provider migration tests verify that changing the configured default affects
  new Payments only; existing Payments retain their persisted provider route.
- Aggregate tests cover multiple provider transaction ids under one merchant
  reference, including a declined transaction followed by an approved retry.
- Expiration tests prove that no new transaction may start after checkout
  expiration, a known pending transaction remains valid, and a trusted late
  approval can move `expired` to `verified`.
- Late approval after another Payment confirmed the Order records the Payment
  and operations signal without overwriting confirmation or repeating handoff.
- Legacy migration tests backfill `legacy_generic` identity, preserve existing
  generic references, and prove grandfathered rows never resolve to Wompi.
- Customer return data alone cannot verify a Payment, confirm an Order, or
  trigger fulfillment-provider handoff.
- Orders are not marked as paid without verified payment provider confirmation.

### Provider Handoff Integrity

- Provider payloads are generated only from persisted backend data.
- Tests verify that:
  - frontend input is not directly forwarded to provider
  - all required production fields are present
  - payload structure matches expected contract

### Data Isolation

- Users cannot:
  - access other users’ orders
  - access other users’ addresses
  - infer existence of other users’ resources via error messages

### Admin Protection

- Non-admin users cannot:
  - modify products
  - modify kits
  - modify pricing rules
  - update order status
- Admin actions are logged.

## State Mutation Guarantees

Security-sensitive tests must verify that rejected requests do not mutate
application state.

For any rejected request:

- no database records are created
- no existing records are modified
- no external side effects are triggered, such as provider handoff calls, payment
  provider calls, emails, file writes, or other outbound requests

Examples:

- unauthorized order access does not update business records or create
  misleading audit entries
- invalid checkout does not create a pending order
- failed payment webhook does not update order status

## Idempotency and Replay Protection

Endpoints that create or mutate critical state must be resilient to retries and
duplicate requests.

Examples:

- checkout/order creation
- payment confirmation webhooks
- provider order submission

Tests should verify:

- duplicate requests do not create duplicate orders unless intended
- an authenticated webhook retry after a simulated lost successful response
  receives HTTP 200 without reapplying state changes or external side effects
- concurrent duplicate delivery commits one event/effect set and acknowledges
  the committed duplicate
- authentication is checked before duplicate acknowledgement
- distinct provider transactions under one merchant reference are not
  incorrectly rejected as webhook replays
- idempotency keys (if implemented) behave correctly

## Abuse and Rate Limiting

Where rate limiting or throttling is implemented, tests should verify:

- excessive requests are rejected or throttled
- critical endpoints are protected:
  - login
  - checkout
  - pricing/quote endpoints
  - payment confirmation

At minimum, service-level protections (such as request guards) should be tested.

## Data Leakage Prevention

Tests should verify that API responses do not expose:

- internal identifiers not part of the public API contract
- sensitive fields (tokens, secrets, internal flags)
- unnecessary personal data

Error responses should not reveal:

- whether a resource exists for another user
- internal system details
- stack traces in production mode

## Secrets and Environment Safety

Tests and configuration must ensure:

- no real credentials are used in tests
- environment variables can be overridden safely in tests
- missing required environment variables fail fast

Test environments should not depend on production secrets.
