# PlacamIA Security Architecture

## Purpose

Security must be part of PlacamIA's foundation, not an afterthought. This document defines the baseline security architecture for the MVP and future production environment.

PlacamIA is a mobile-first application for designing, quoting, purchasing, and tracking industrial safety signage. The MVP includes catalog, kits, rules-based customization, pricing, checkout, and order tracking.

## Security Principles

1. Secure by default.
2. Never trust the frontend.
3. Server owns pricing, authorization, and order integrity.
4. No secrets in code.
5. Least privilege everywhere.
6. Logs must help investigation without exposing sensitive data.
7. Security-relevant behavior must be tested.

## Current Security Priorities

### 1. Authentication and Authorization

The backend must support authentication before sensitive endpoints are added.

Initial roles:

- `user`
- `admin`

Rules:

- Public endpoints may expose catalog and product data.
- User-specific endpoints require authentication.
- Admin endpoints require explicit admin authorization.
- Users may only access their own orders, carts, addresses, and profile data.

Never rely on mobile-app controls for authorization.

Current backend authentication resolves users through a reusable FastAPI
dependency that verifies backend-signed bearer tokens and loads the current
active user from the database. Protected endpoints must use this dependency
instead of accepting `user_id`, `role`, `is_admin`, or ownership fields from
frontend payloads.

`AUTH_TOKEN_SECRET` must be provided by the runtime environment. Example files
may include placeholder local values, but real token secrets must not be
committed or logged.

### 2. Server-Side Pricing Integrity

Pricing must always be calculated by the backend.

The frontend may send:

- product id
- material id
- size id
- quantity
- kit id
- customization options

The frontend must never be trusted to send final prices, discounts, taxes, or totals.

The backend must recalculate:

- base price
- kit discount
- volume discount
- subtotal
- shipping
- final total

Any checkout/order creation endpoint must validate that the selected options still exist, are active, and are allowed.

### 3. Input Validation

All request bodies must use strict schemas.

Validation must cover:

- required fields
- allowed enum values
- quantity limits
- string length limits
- UUID format
- positive numeric values
- allowed product/material/size combinations

Reject unknown or unexpected fields where practical.

### 4. Secrets Management

No secrets may be committed to the repository.

Secrets include:

- database passwords
- JWT signing keys
- payment provider credentials
- AWS credentials
- S3 bucket credentials
- API keys
- SMTP credentials

Local development may use `.env`, but `.env` must remain ignored by git.

Production secrets must use environment variables or AWS Secrets Manager.

### 5. Database Security

Use Alembic for schema changes.

Database rules:

- Use migrations for every schema change.
- Avoid raw SQL unless necessary.
- Use parameterized queries.
- Do not store payment card data.
- Store only necessary personal data.
- Add indexes carefully for lookup fields, not sensitive data exposure.
- Enable backups before production.

### 6. Payment Security

PlacamIA must not store credit/debit card data.

Payment flow must use a payment provider. The backend should only store:

- stable payment provider code and merchant reference
- optional provider checkout reference and checkout expiration
- canonical Payment status
- provider transaction references and normalized transaction observations
- minimal provider event/replay references and payload hashes
- order id
- amount paid
- currency
- timestamps

Raw provider payloads, signatures, provider secrets, card/bank credentials, and
unnecessary customer data must not be stored. A raw payload may be processed in
memory long enough to verify authenticity and calculate a safe audit hash.

Payment webhooks use provider-specific routes. Each route must apply that
provider's exact signature/checksum algorithm before parsing the event into a
normalized application event. Selecting verification from a global current
provider is forbidden because existing Payments must continue using their
persisted provider after a default-provider change.

For Wompi:

- the public key, integrity secret, and event secret have separate purposes
- integrity signatures are generated only from backend-owned reference, amount,
  currency, expiration, and secret values
- event checksums are verified from the exact ordered event properties,
  timestamp, and configured event secret required by Wompi
- secrets and full signed checkout URLs must not be logged
- the browser return URL and returned transaction id are untrusted navigation
  data and cannot verify a Payment without backend reconciliation

Never fulfill an order based only on frontend confirmation.

Payment webhook replay protection is durable. After a webhook signature and
trusted payment-event fields are validated against backend Order and Payment
state, the backend stores a minimal replay key containing the event reference,
payload hash, source, received timestamp, and linked Order/Payment identifiers
when available. Raw webhook payloads, signatures, secrets, card data, and full
payment details must not be stored in replay records.

The replay key, provider transaction/event mutation, Payment mutation, and
Order mutation are committed in one database transaction before fulfillment-
provider handoff is attempted. An authenticated duplicate whose event reference
and payload hash match an already-committed event returns HTTP 200
`already_processed`. It must not reapply transaction, Payment, Order, or
provider handoff state. This acknowledgement is required when the original HTTP
response was lost and the provider retries a successfully committed event.

Missing or invalid authentication, replay-reference reuse with a different
payload hash, and failures before commit return non-2xx without mutation. A
replay conflict must emit a safe security signal. Authentication is always
verified before a delivery is treated as an acknowledged duplicate.

One merchant reference may have multiple provider transaction ids. Replay
protection and uniqueness must distinguish those transactions. A failed or
declined transaction must not terminalize a retryable Payment aggregate, while
an approved transaction must match the persisted merchant reference, amount,
and currency before it can verify Payment.

`checkout_expires_at` blocks new customer transaction starts; it is not proof
that a provider-accepted transaction cannot settle. A Payment displayed as
customer-terminal `expired` may move to `pending` or `verified` only from a
trusted provider webhook or backend reconciliation. A matching late approval
must be persisted even if another Payment already confirmed the Order; Order
confirmation and fulfillment handoff remain exactly-once, and the duplicate
financial outcome produces a safe operations signal.

Legacy provider-neutral Payments are assigned `provider_code =
"legacy_generic"` during migration and must never resolve to the Wompi adapter.
Historical generic references remain preserved rather than being relabeled as
Wompi transaction identity.

### 7. File and Image Security

Product images, previews, or generated assets must be stored securely.

Rules:

- S3 buckets must not be public by default.
- Use signed URLs when private access is required.
- Validate file type and size before accepting uploads.
- Do not allow arbitrary file extensions.
- Do not execute uploaded files.

### 8. Logging and Monitoring

Logs must include enough information to debug and investigate issues.

Log:

- auth failures
- authorization failures
- order creation
- payment webhook events
- unexpected pricing mismatches
- admin actions
- provider order transmission events

Do not log:

- passwords
- access tokens
- refresh tokens
- payment card data
- full secrets
- payment integrity signatures or concatenated signature preimages
- full signed checkout or handoff URLs
- unnecessary personal data

### 9. API Protection

All production API traffic must use HTTPS.

API Gateway should enforce:

- throttling
- request size limits
- basic abuse protection
- structured access logs

Rate limiting should be applied to:

- login
- registration
- checkout
- payment confirmation
- quote/pricing endpoints

### 10. Provider Integration Security

Orders sent to a manufacturing provider must be validated before transmission.

The order payload must include:

- order id
- product ids
- material
- size
- quantity
- final approved price
- production specs
- delivery information
- customer contact data needed for fulfillment only

The backend must generate the provider payload from trusted database records,
not directly from frontend input.

### 11. Admin Security

Admin features must be protected from the start.

Admin actions include:

- product creation/update
- kit creation/update
- price changes
- order status changes
- provider integration actions

Every admin action must be logged. Admin endpoints must use the reusable admin
authorization dependency after the current user has been resolved from a
backend-verified bearer token and loaded from the database. Admin checks must
read the backend-owned user role and must not trust frontend-supplied `role`,
`is_admin`, `user_id`, or ownership fields.

Audit logs must include:

- authenticated admin user id
- stable action name
- affected resource type
- affected resource id when available
- structured context needed for incident investigation
- creation timestamp

Audit logs must not include passwords, access tokens, refresh tokens, secrets,
full payment card data, or full environment variables. Audit log writes should
be part of the same database transaction as the admin change when possible so
the business change and its audit record succeed or fail together.

Audit event details are redacted before persistence. Key-based redaction is the
primary protection and currently redacts any key containing one of these
case-insensitive fragments:

- `password`
- `token`
- `secret`
- `credential`
- `authorization`
- `card`
- `payment_card`
- `jwt`
- `refresh_token`
- `access_token`
- `api_key`
- `private_key`
- `signature`
- `signed_url`
- `handoff_url`
- `checkout_url`
- `environment`

For Wompi, keys such as `wompi_integrity_secret`, `signature_preimage`,
`signature:integrity`, `signed_checkout_url`, and `handoff_url` are therefore
redacted before audit persistence. Application and SQL logs must avoid these
values at the source. The `pub_test_` and `pub_prod_` prefixes identify public
checkout keys, while `test_integrity_` and `prod_integrity_` identify secrets;
prefix validation must not log either configured value.

Value-based redaction is intentionally deterministic and conservative. It only
redacts explicitly documented token/key patterns:

- JWT-like strings with three dot-separated segments whose decoded header is a
  JSON object containing `alg` or `typ`
- PEM private-key blocks containing `BEGIN`, `PRIVATE KEY`, and `END` markers

This JWT value detection is intentionally narrow. It does not guarantee
redaction of malformed, truncated, partially corrupted, or embedded token
fragments that may still contain sensitive information. The primary control is
still to avoid logging authorization headers, raw request bodies, bearer
tokens, secrets, or sensitive payloads. Broader token-fragment redaction should
be handled as dedicated hardening work when request/error logging expands. Any
change to the JWT-like value rule must keep this documented shape in sync with
tests so redaction does not expand accidentally.

Do not add generic secret detection or entropy-based scanning to audit logs
without a dedicated issue and tests. Broad heuristic scanning risks hiding
useful incident context and making audit behavior difficult to reason about.

Role handling remains string-based for the MVP, with supported values defined
in the backend `UserRole` constants. Admin authorization must continue to use
the reusable admin dependency, which compares the authenticated database user
role to `UserRole.ADMIN`. No full RBAC system or role migration is required
until a planning document and implementation issue define that expansion. If a
future admin API accepts role values as input, that API must add explicit
request validation for allowed role values instead of relying solely on backend
constants or downstream comparisons.

### 12. Security Testing Requirements

Security-sensitive code must include tests.

Required test categories:

- user cannot access another user's order
- non-admin cannot access admin endpoints
- backend ignores frontend-supplied price
- invalid product/material/size combinations are rejected
- inactive products cannot be ordered
- payment webhook with invalid signature is rejected
- protected endpoints reject unauthenticated requests

### 13. Pre-Launch Security Checklist

Before public launch:

- [ ] No secrets committed
- [ ] `.env` ignored
- [ ] HTTPS configured
- [ ] API Gateway throttling enabled
- [ ] RDS backups enabled
- [ ] S3 buckets private
- [ ] Payment webhooks verified
- [ ] Admin endpoints protected
- [ ] Security tests passing
- [ ] Basic monitoring enabled
- [ ] Error logs reviewed
- [ ] Dependency scan configured
- [ ] Incident contact list defined

## Known MVP Risks

The MVP includes dynamic pricing, checkout, order tracking, and provider
fulfillment. These are high-value attack surfaces and must be treated as
security-critical.

The most important risks are:

1. Price manipulation
2. Unauthorized order access
3. Payment spoofing
4. Provider order corruption
5. Secrets leakage
6. Abuse of quote/pricing endpoints
7. Excess AWS cost due to bot traffic

## Future Security Enhancements

Post-MVP:

- AWS WAF
- audit log dashboard
- anomaly detection
- admin MFA
- penetration testing
- formal backup restore drills
- privacy/data retention policy
