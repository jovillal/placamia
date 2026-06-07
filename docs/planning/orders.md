# Orders

## Goal

Create and track customer orders from validated backend state.

Orders are the bridge between the customer purchase flow, payment verification,
provider adapter handoff, production, shipment, and customer tracking.

The MVP follows Path A: orders are created from backend-validated direct
checkout state for fully parametrizable products and kits. RFQ/provider quote
confirmation is not part of the MVP order creation path.

## Core Principles

- Orders must be created from backend-validated data.
- Orders must not trust frontend-provided totals.
- Orders must have an explicit status lifecycle.
- Rejected order requests must not mutate database state.
- Provider adapter payloads must be generated from persisted order data.
- Provider handoff, acceptance, and rejection must go through the provider
  adapter boundary after verified payment.
- Customer cancellation after payment is a request, not an automatic order
  mutation.

## Flow

1. User confirms checkout intent
2. Backend validates pricing, design, direct-checkout eligibility, and
   cancellation/refund terms acknowledgement
3. Backend creates Order and OrderItems
4. Payment flow confirms or rejects payment
5. Paid/confirmed order becomes eligible for provider adapter handoff
6. Provider adapter records provider acceptance or rejection of the paid order
7. Provider/production/shipment status updates order state
8. User can track order status

## Status Lifecycle

Initial MVP lifecycle:

draft → confirmed → sent_to_provider → accepted → in_production → ready_for_pickup → shipped → delivered

Terminal/cancelled state:

cancelled

Cancellation request state:

cancellation_requested

Customer cancellation after payment moves to `cancellation_requested` and must
be approved or rejected according to the documented cancellation/refund policy.

See `docs/flows/main-flow.md`, `docs/flows/provider-fulfillment-flow.md`, and
`docs/product/provider-handoff.md`.

Provider adapter boundary:

- `docs/planning/provider-adapter-contract.md`

Related validation docs:

- `docs/validation/commercial-model.md`
- `docs/validation/pricing-model.md`

### Valid Transitions

Path A order status transitions are deterministic and backend-owned:

- `draft -> confirmed` only after verified payment-provider confirmation.
- `confirmed -> sent_to_provider` only after the provider adapter handoff is
  sent for the paid order.
- `sent_to_provider -> accepted` only when the provider adapter records
  provider acceptance.
- `sent_to_provider -> cancelled` when the provider adapter records provider
  rejection, followed by cancellation/refund handling.
- `accepted -> in_production` when production starts.
- `in_production -> ready_for_pickup` when the package is prepared for pickup
  with QR handling.
- `ready_for_pickup -> shipped` only after a carrier QR pickup scan or
  authorized operator fallback.
- `shipped -> delivered` after delivery confirmation.
- `draft -> cancelled` for pre-payment cancellation, payment failure, or
  authorized administrative cancellation.
- `confirmed|accepted|in_production -> cancellation_requested` when the paid
  customer requests cancellation.
- `cancellation_requested -> cancelled` after authorized cancellation/refund
  approval.
- `cancellation_requested -> confirmed|accepted|in_production` only when the
  cancellation request is rejected and the order returns to the status from
  which the cancellation was requested.

`delivered` and `cancelled` are terminal states. Invalid transitions must be
rejected without mutating persisted order state.

### Order Model Requirements For #30

The database implementation in #30 must persist enough order state to support
tracking, payment verification, provider handoff, auditability, and security
without trusting frontend-owned values.

Required Order fields:

- backend-generated primary key
- authenticated customer owner id
- canonical status from the Path A lifecycle
- cancellation request source status when status is `cancellation_requested`
- backend-calculated subtotal, tax/fee amounts if applicable, discounts if
  applicable, total amount, and currency
- payment provider reference and verified payment timestamp when confirmed
- provider handoff reference, assigned provider id, and handoff timestamp when
  sent
- cancellation/refund terms policy identifier or version acknowledged before
  payment
- customer-safe tracking fields needed by the status endpoint
- created and updated timestamps

Security requirements:

- order ownership must come from the authenticated request, not a frontend
  `user_id`
- totals must be calculated by backend pricing and copied from validated
  checkout state
- provider handoff data must be generated from persisted Order and OrderItems
- provider acceptance/rejection must arrive through the provider adapter
  boundary
- customer cancellation after payment must not directly write `cancelled`
- rejected mutations must leave the order and its items unchanged

### OrderItem Model Requirements For #30

OrderItems are immutable purchased item snapshots. They must preserve the data
needed for payment reconciliation, provider payload generation, and customer
tracking even if catalog products, kits, templates, pricing rules, or provider
fixtures change later.

Required OrderItem fields:

- backend-generated primary key
- parent order id
- item type (`product`, `kit`, or validated `design`)
- product, kit, template, and design references where applicable
- display name and customer-safe description snapshot
- selected material, size, finish, template/customization values, and quantity
- backend-calculated unit price, line subtotal, discounts if applicable, taxes
  or fees if applicable, line total, and currency
- assigned provider id and provider capability/cost reference used for backend
  pricing and handoff
- provider payload snapshot fields needed for manufacturing, excluding
  sensitive internal-only or raw frontend data
- created timestamp

OrderItem records must not be recomputed from mutable catalog state during
tracking or provider handoff. Corrections must be explicit order adjustments or
new documented flows, not silent snapshot rewrites.

## Scope

- Order status lifecycle
- Order and OrderItem models
- Order creation endpoint
- Order status endpoint
- Order payload/service preparation for provider adapter handoff
- Cancellation request state handling
- Shipment status transition from QR pickup scan or authorized fallback


## Related Endpoints

- POST /api/v1/orders
- GET /api/v1/orders/{id}/status

See docs/api/endpoint-structure.md.

## Child Issues

- #29 Define order status lifecycle
- #30 Create Order and OrderItem models, migrations, and tests
- #31 Create POST order endpoint with tests
- #32 Create GET order status endpoint with tests
- #33 Create GET order status endpoint with tests
- #35 Implement order export service
- #61 Send order to provider

Note: #32 and #33 currently overlap and should be reconciled before
implementation.

## Future Issues

- Future issue required: add order ownership and authorization checks
- Future issue required: add tests that rejected order creation does not mutate
  database state
- Future issue required: add idempotency/retry protection for order creation
- Future issue required: add explicit link between successful payment and order
  confirmation
- Future issue required: define and test cancellation request policy by order
  state
- Future issue required: define QR pickup scan or operator fallback behavior for
  `ready_for_pickup` to `shipped`

## Constraints

- Do not create orders from unvalidated frontend data.
- Do not accept frontend-calculated totals.
- Do not expose another user’s orders.
- Do not mark orders as paid without verified payment provider confirmation.
- Keep provider adapter handoff separate from order creation.
- Trigger provider handoff only through the provider adapter boundary after
  verified payment.
- Provider acceptance or rejection must be recorded through the provider
  adapter boundary, not from raw frontend input.
- Do not create orders for inactive, unavailable, manual-quote-only, or
  non-priceable products, kits, or designs.
- Do not automatically cancel paid orders from customer input alone.
- Do not transition to `shipped` without a valid QR pickup scan event or
  authorized operator fallback.

## Security Considerations

Orders are security-sensitive because they affect payment, production, and customer data.

## Required protections:

- authenticated user required for user-specific order access
- ownership checks for order status/details
- backend-calculated totals only
- validation of products, kits, designs, quantities, and active status
- no mutation on rejected requests
- no provider handoff from raw frontend payload
- no provider handoff before verified payment
- no provider acceptance or rejection from raw frontend payload
- no cross-user visibility into cancellation requests or shipment details

See docs/architecture/security.md and docs/architecture/testing.md.

## Testing Requirements

Orders must include tests for:

- valid order creation
- invalid input rejected
- frontend-supplied total ignored
- unauthenticated access rejected
- user cannot access another user’s order
- rejected order creation does not create records
- status endpoint returns correct lifecycle state
- paid customer cancellation request does not directly cancel the order
- provider handoff is only attempted through the adapter after verified payment
- provider acceptance/rejection is recorded only through the adapter boundary
- QR shipment transition requires valid event or authorized fallback


## Done When

- Order lifecycle is documented and implemented
- Orders and order items are persisted correctly
- Order creation uses backend-validated pricing/design data
- Order status can be retrieved by the owning user
- Cancellation and shipment states match the canonical flow
- Tests cover accepted and rejected behavior
