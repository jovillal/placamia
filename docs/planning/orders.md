# Orders

## Goal

Create and track customer orders from validated backend state.

Orders are the bridge between the customer purchase flow, payment verification,
provider handoff, production, shipment, and customer tracking.

The MVP follows Path A: orders are created from backend-validated direct
checkout state for fully parametrizable products and kits. RFQ/provider quote
confirmation is not part of the MVP order creation path.

## Core Principles

- Orders must be created from backend-validated data.
- Orders must not trust frontend-provided totals.
- Orders must have an explicit status lifecycle.
- Rejected order requests must not mutate database state.
- Provider export payloads must be generated from persisted order data.
- Customer cancellation after payment is a request, not an automatic order
  mutation.

## Flow

1. User confirms checkout intent
2. Backend validates pricing, design, direct-checkout eligibility, and
   cancellation/refund terms acknowledgement
3. Backend creates Order and OrderItems
4. Payment flow confirms or rejects payment
5. Paid/confirmed order becomes eligible for provider handoff
6. Assigned provider accepts or rejects the paid order
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

Related validation docs:

- `docs/validation/commercial-model.md`
- `docs/validation/pricing-model.md`

## Scope

- Order status lifecycle
- Order and OrderItem models
- Order creation endpoint
- Order status endpoint
- Order export/service preparation for provider handoff
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
- Keep provider export separate from order creation.
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
- QR shipment transition requires valid event or authorized fallback


## Done When

- Order lifecycle is documented and implemented
- Orders and order items are persisted correctly
- Order creation uses backend-validated pricing/design data
- Order status can be retrieved by the owning user
- Cancellation and shipment states match the canonical flow
- Tests cover accepted and rejected behavior
