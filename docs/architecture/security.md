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

- payment provider reference
- payment status
- order id
- amount paid
- currency
- timestamps

Webhook endpoints must verify payment provider signatures.

Never fulfill an order based only on frontend confirmation.

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
