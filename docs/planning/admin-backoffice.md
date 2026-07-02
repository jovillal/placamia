# Admin / Backoffice

## Goal

Define the administrative surface needed to manage PlacamIA safely without
mixing customer-facing catalog behavior with privileged mutations.

Admin/backoffice work must build on the existing authentication, authorization,
and audit logging foundation.

## Scope

- Admin endpoint grouping and authorization requirements
- Admin-only product, kit, price, order, provider, and user workflows
- Audit logging for security-relevant admin actions
- Current-user and role handling for protected admin routes

## Related Docs

- `docs/planning/security.md`
- `docs/planning/provider.md`
- `docs/tasks/checkout.md`
- `docs/architecture/security.md`
- `docs/api/endpoint-structure.md`
- `docs/api/api-style.md`

## Endpoints

### Path Grouping Decision

Path A uses a hybrid grouping rule:

- Domain-local paths may be used for narrowly scoped operational mutations that
  act on one domain resource and already have a clear customer-safe resource
  boundary, such as order cancellation review or provider fulfillment events.
- `/api/v1/admin/...` is reserved for broader administrative management
  surfaces such as catalog maintenance, pricing table maintenance, users,
  operational dashboards, and cross-resource review queues.
- Existing domain-local admin/operator-like endpoints remain in place. Do not
  rename them into `/api/v1/admin/...` without a dedicated compatibility issue.
- Every admin/operator mutation must document its authorization dependency and
  audit behavior before it can be considered acceptable.

### Existing Endpoint Inventory

These implemented endpoints are acceptable for the current Path A MVP because
their route descriptions, docstrings, and tests document backend-derived admin
authorization and audit logging behavior.

| Method | Path | Purpose | Actor | Authorization | Audit behavior | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| `POST` | `/api/v1/provider/orders/{order_id}/acceptance` | Record provider acceptance or rejection for an order already sent to the provider adapter. | Admin acting as trusted operations ingester | `require_admin_user`; frontend role, ownership, status, and reason claims are not trusted. | `provider.acceptance_decision.record` admin audit entry committed with order transition. | Implemented and acceptable |
| `POST` | `/api/v1/provider/orders/{order_id}/production-progress` | Record provider production progress such as production start or package-ready. | Admin acting as trusted operations ingester | `require_admin_user`; frontend/customer status claims are rejected. | `provider.production_progress.record` admin audit entry committed with order transition. | Implemented and acceptable |
| `POST` | `/api/v1/provider/orders/{order_id}/shipment` | Record carrier QR pickup scan or authorized operator fallback shipment event. | Admin acting as trusted operations ingester | `require_admin_user`; frontend/customer status claims are rejected. | `provider.shipment.record` admin audit entry committed with order transition. | Implemented and acceptable |
| `POST` | `/api/v1/provider/orders/{order_id}/delivery` | Record trusted delivery confirmation for shipped orders. | Admin acting as trusted operations ingester | `require_admin_user`; frontend/customer status claims are rejected. | `provider.delivery.record` admin audit entry committed with order transition. | Implemented and acceptable |
| `POST` | `/api/v1/orders/{order_id}/cancellation-request/approve` | Approve a pending customer cancellation request. | Admin reviewer | `require_admin_user`; frontend role, ownership, status, and resolution claims are rejected by schema/service boundaries. | `order.cancellation.approve` admin audit entry committed with order transition. | Implemented and acceptable |
| `POST` | `/api/v1/orders/{order_id}/cancellation-request/reject` | Reject a pending customer cancellation request and restore the prior paid state. | Admin reviewer | `require_admin_user`; frontend role, ownership, status, and resolution claims are rejected by schema/service boundaries. | `order.cancellation.reject` admin audit entry committed with order transition. | Implemented and acceptable |

The customer-facing cancellation request endpoint is intentionally not an
admin/operator endpoint. It is authenticated through `get_current_user`,
enforces ownership, and records a customer audit event, but it is not part of
the admin/operator matrix.

### Minimum Operating Surface

The Path A admin/operator surface should stay intentionally small. It exists to
let PlacamIA safely operate paid orders, inspect stuck states, and prove what
happened without introducing a broad backoffice product before the MVP needs
one.

Minimum implemented surface:

- Provider acceptance/rejection recording after paid-order handoff.
- Provider production progress recording for `accepted -> in_production` and
  `in_production -> ready_for_pickup`.
- Shipment recording for carrier QR pickup scan or authorized operator
  fallback.
- Delivery confirmation recording for shipped orders.
- Cancellation request approval/rejection for paid order states that support
  customer cancellation requests.

Minimum likely gaps before operational hardening:

- Provider handoff retry for confirmed paid orders whose adapter transmission
  failed before `sent_to_provider`.
- Provider handoff status reconciliation for handed-off orders whose local
  state may drift from provider-side state.
- Operator-facing inspection or documented smoke procedure for stuck paid
  orders, using existing read surfaces where possible before adding new
  endpoints.

### QA, Docs, And Examples Minimums

Every new admin/operator mutation must satisfy the following before it is
considered ready for review:

- Requires backend-derived admin authorization.
- Rejects frontend `role`, `is_admin`, ownership, status, payment,
  provider-reference, and lifecycle claims.
- Rejects invalid lifecycle states without mutating Order, Payment, provider,
  or audit-log state.
- Writes a minimal admin audit log for successful security-relevant mutations.
- Does not alter payment confirmation fields unless a payment-specific planning
  document and issue explicitly define that behavior.
- Is listed in `docs/api/endpoint-structure.md`.
- Updates this admin/operator matrix when the endpoint is implemented or
  behavior changes.
- Includes at least one happy-path test and one rejection/no-mutation test.
- Includes API examples or a documented smoke path when manual QA is expected.

Minimum operator smoke path:

1. Create and pay a Path A order through the existing checkout/payment flow.
2. Confirm the order reaches `sent_to_provider` after provider handoff.
3. Record provider acceptance.
4. Record production start.
5. Record package ready for pickup.
6. Record shipment through QR pickup scan or authorized fallback.
7. Record delivery confirmation.
8. Verify payment confirmation fields remain unchanged through fulfillment
   mutations.

### Required Future Endpoint Candidates

These are not implemented by this definition issue. Each needs a scoped
follow-up issue before runtime code is added.

| Candidate | Purpose | Preferred grouping | Actor | Authorization and audit expectation | Source | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| Provider handoff retry | Retry failed provider handoff attempts without duplicating provider orders. | Domain-local under `/api/v1/provider/...` unless a broader admin queue is introduced. | Admin/operator | Backend-derived admin/operator authorization; audit retry request, idempotency key, previous handoff state, and result. | `docs/planning/provider.md` | Gap; future issue required if manual retry is operationally needed |
| Provider handoff status reconciliation | Reconcile provider-side status for previously handed-off orders. | Domain-local under `/api/v1/provider/...` for single-order reconciliation; `/api/v1/admin/...` for batch dashboards. | Admin/operator or trusted backend job | Backend-derived authorization for manual reconciliation; audit manual mutations; automated jobs need durable event logging. | `docs/planning/provider.md`, `docs/planning/provider-adapter-contract.md` | Gap; future issue required |
| Provider availability maintenance | Update local/mock or real-provider availability data if seed/manual-only maintenance is insufficient. | `/api/v1/admin/provider-availability/...` or equivalent admin grouping. | Admin/operator | Backend-derived admin authorization; audit availability changes; ignore frontend provider, price, and eligibility claims. | `docs/tasks/catalog.md`, `docs/planning/provider.md` | Deferrable until validation/seed strategy requires runtime maintenance |
| Catalog/product/kit administration | Maintain products, kits, and direct-checkout visibility/purchasability outside seed data. | `/api/v1/admin/catalog/...` | Admin | Backend-derived admin authorization; audit product, kit, price, discount, visibility, and eligibility changes. | `docs/planning/admin-backoffice.md`, `docs/tasks/catalog.md` | Deferrable; future issue required before runtime CRUD |
| Pricing table maintenance | Maintain backend-owned pricing data if pricing becomes database-backed instead of seed/manual-only. | `/api/v1/admin/pricing/...` | Admin | Backend-derived admin authorization; audit price/discount changes; never trust frontend totals. | `docs/planning/security.md`, `docs/tasks/checkout.md` | Deferrable until pricing persistence is scoped |
| Refund/payment resolution | Resolve refunds or payment-provider exceptions after cancellation/rejection policy is defined. | `/api/v1/admin/payments/...` | Admin | Backend-derived admin authorization; audit without card data or full payment payloads. | `docs/planning/payments.md`, `docs/tasks/checkout.md` | Out of scope for Path A endpoint minimum |
| Provider payout/invoicing | Automate provider payout, invoicing, or SLA consequences. | `/api/v1/admin/accounting/...` if ever implemented. | Admin/accounting role after future RBAC decision | Requires future authorization model and audit policy. | `docs/planning/provider.md`, `docs/tasks/checkout.md` | Explicitly deferred |
| Carrier API integration | Receive carrier pickup/delivery events directly from a carrier integration. | Dedicated integration path after carrier validation. | Trusted backend integration | Signature/auth validation and durable event logging required. | `docs/flows/provider-fulfillment-flow.md`, `docs/planning/provider.md` | Explicitly deferred |

### Follow-Up Issue List

Create scoped implementation issues only when the relevant operational need is
confirmed:

- Add admin/operator retry endpoint for failed provider transmissions if manual
  retry is needed.
- Define and implement provider handoff status reconciliation.
- Define provider availability maintenance if local/mock fixture and seed-data
  updates are not enough.
- Define admin catalog/product/kit maintenance after validation findings
  establish the MVP data ownership model.
- Define pricing maintenance only after pricing persistence is scoped.

## Child Issues

Definition and follow-up planning:

- #68 Define minimum admin/operator endpoints for Path A operations

Open, but needs issue-template cleanup before implementation:

- #71 Authentication/current-user
- #72 Authorization/audit logging

## Constraints

- Admin endpoints must require admin authorization.
- Admin mutations must be auditable when they affect products, kits, prices,
  discounts, orders, provider integration, or users.
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
