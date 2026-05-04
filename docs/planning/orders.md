# Orders

## Goal

Create and track customer orders from validated backend state.

Orders are the bridge between the customer purchase flow, payment verification,
provider handoff, production, shipment, and customer tracking.

## Core Principles

- Orders must be created from backend-validated data.
- Orders must not trust frontend-provided totals.
- Orders must have an explicit status lifecycle.
- Rejected order requests must not mutate database state.
- Supplier/export payloads must be generated from persisted order data.

## Flow

1. User confirms checkout intent
2. Backend validates quote/pricing/design data
3. Backend creates Order and OrderItems
4. Payment flow confirms or rejects payment
5. Paid/confirmed order becomes eligible for provider handoff
6. Provider/production status updates order state
7. User can track order status

## Status Lifecycle

Initial MVP lifecycle:

draft → confirmed → sent_to_provider → accepted → in_production → shipped → delivered

Terminal/cancelled state:

cancelled

See docs/product/provider-handoff.md.

## Scope

- Order status lifecycle
- Order and OrderItem models
- Order creation endpoint
- Order status endpoint
- Order export/service preparation for provider handoff


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

## Constraints

- Do not create orders from unvalidated frontend data.
- Do not accept frontend-calculated totals.
- Do not expose another user’s orders.
- Do not mark orders as paid without verified payment provider confirmation.
- Keep provider export separate from order creation.

## Security Considerations

Orders are security-sensitive because they affect payment, production, and customer data.

## Required protections:

- authenticated user required for user-specific order access
- ownership checks for order status/details
- backend-calculated totals only
- validation of products, kits, designs, quantities, and active status
- no mutation on rejected requests
- no supplier handoff from raw frontend payload

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


## Done When

- Order lifecycle is documented and implemented
- Orders and order items are persisted correctly
- Order creation uses backend-validated pricing/design data
- Order status can be retrieved by the owning user
- Tests cover accepted and rejected behavior
