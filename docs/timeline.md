# PlacamIA MVP Status And Remaining Work

## Product Direction

The MVP follows Path A: direct checkout for active products and kits that are
fully parametrizable, compatible with provider adapter responses, and
deterministically priceable by backend-owned rules.

RFQ/manual-quote flows, AI-assisted customization, exact inventory, provider
dashboards, and automated accounting remain outside the MVP.

The canonical behavior and lifecycle are defined in
`docs/flows/main-flow.md`. This document records implementation status and
remaining delivery work; it does not redefine that flow.

## Implemented Baseline

### Platform And Security

- FastAPI modular monolith, PostgreSQL/SQLAlchemy persistence, Alembic
  migrations, and pytest test architecture.
- Reusable bearer-token current-user resolution, persisted roles, admin
  authorization, and audit logging for protected mutations.
- Security-sensitive rejection coverage for authentication, ownership,
  pricing, checkout, payments, orders, and provider/admin behavior.

### Catalog, Kits, Templates, And Designs

- Public categories, product listing/detail, filters, provider-backed
  availability, direct-checkout eligibility, and lead-time signals.
- Kit models and public listing with customer-safe required-content summaries
  and backend-derived purchasability.
- Template, TemplateField, and Design persistence plus deterministic Design
  customization validation.
- Public active Template list/detail endpoints with customer-safe active field
  definitions and deterministic ordering.
- Authenticated Design creation and owner-only retrieval with backend-validated
  customization and customer-safe responses.

### Pricing, Checkout, Orders, And Payments

- Deterministic Product, fixed-content Kit, and owned persisted Design pricing
  previews with backend-owned totals and trusted provider cost/capability
  inputs.
- Checkout eligibility and cancellation/refund terms acknowledgement.
- Authenticated draft order creation, immutable OrderItem snapshots, and
  owner-only order-status retrieval.
- Provider-neutral payment initialization, signed webhook verification,
  durable replay protection, Payment persistence, and order confirmation only
  after verified payment.

### Provider Handoff And Fulfillment

- Deterministic local/mock provider adapter and paid-order handoff.
- Provider handoff trace fields and retry-safe failure behavior.
- Provider acceptance/rejection, production progress, QR/operator shipment,
  delivery, and paid-order cancellation-request lifecycle behavior.

### Mobile

- Expo placeholder scaffold under `apps/mobile`.
- Static/mock Path A screen map and backend dependency contract in
  `docs/planning/mobile-placeholder.md`.
- No production backend wiring, persisted mobile session, real payment SDK, or
  production customer data is included in the placeholder.

## Current MVP Milestone

GitHub milestone: `Current MVP`.

### Active Corrections And Validation

- #176 keeps mixed active/inactive kit contents non-purchasable while returning
  a customer-safe aggregate eligibility reason.
- #99 validates reference-provider product, pricing, availability, and
  commercial assumptions.
- #111 updates seed data after #99 supplies approved validation findings.

### Remaining Customer Contracts

- #179 customer sign-in and token acquisition contract.
- #185 versioned customer-visible cancellation/refund terms source.
- #186 real payment-provider initialization response.
- #187 customer payment-status refresh contract.
- #188 customer order list endpoint.
- #189 full customer order detail endpoint.

These issues are scoped independently. Implementations must continue to follow
the source-of-truth planning documents and security test requirements referenced
by each issue.

## Validation Dependencies

- #99 is HITL and must supply approved commercial/provider findings before
  #111, customer policy content in #185, or provider-specific assumptions in
  #186 are treated as production truth.
- Authentication provider/session choices for #179 and the real payment
  provider contract for #186 require explicit human decisions before
  implementation.
- Local/mock adapters remain the deterministic development boundary while real
  provider contracts are pending.

## Deferred Beyond Current MVP

- RFQ/manual-quote customer flow.
- Real manufacturing-provider status reconciliation and operational dashboard.
- Carrier API integration beyond QR/operator fallback.
- Runtime catalog, kit, availability, and pricing administration unless seed
  and fixture maintenance proves insufficient.
- Refund execution, provider payout, invoice automation, and accounting tools.
- AI, AR, 3D rendering, collaborative projects, and credit systems.

## Completion Check

Before declaring the MVP ready for production integration:

- resolve or explicitly defer every issue in `Current MVP`;
- run the full backend and mobile validation suites;
- verify FastAPI `/docs` and the endpoint inventory;
- verify security-sensitive rejection paths do not mutate state or trigger
  external side effects;
- reconcile this status document and the mobile dependency map with the merged
  implementation.
