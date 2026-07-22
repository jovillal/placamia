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
8. User can list their owner-scoped order summaries
9. User can track an owned order's status

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
- Customer Order list endpoint
- Customer Order detail endpoint
- Order status endpoint
- Order payload/service preparation for provider adapter handoff
- Provider handoff transmission success recording
- Cancellation request state handling
- Shipment status transition from QR pickup scan or authorized fallback

Current state:

- Order and OrderItem models, migrations, repositories, and service tests are
  implemented.
- Authenticated draft order creation from backend-validated checkout state is
  implemented.
- Customer-owned order status retrieval is implemented.
- Paid-order provider payload preparation and local/mock adapter transmission
  are implemented for confirmed orders with verified payment.
- Successful handoff records provider handoff reference, handoff sent
  timestamp, and `sent_to_provider` status.
- Payment webhook processing persists Payment records, writes payment
  confirmation fields for verified events, and moves eligible draft orders to
  `confirmed`.
- Payment webhook replay keys are persisted atomically with Payment and Order
  mutation so replayed event ids do not duplicate confirmation or handoff
  behavior.
- Payment initialization creates or returns a backend-owned Payment attempt for
  eligible draft Orders without confirming the Order or triggering provider
  handoff.
- Until a real payment-provider initialization adapter response is defined,
  the initialized Payment attempt does not carry a provider reference. A later
  verified webhook may therefore persist the provider-referenced verified
  Payment as a separate row while moving the Order out of `draft`, which
  prevents that initialized attempt from being reused through the initialization
  endpoint.
- Paid-order provider handoff orchestration attempts handoff after successful
  payment webhook confirmation. Failed handoff leaves the order `confirmed`
  with payment fields intact and provider handoff success fields empty for
  later retry.
- Provider acceptance/rejection persistence is implemented after successful
  handoff. Acceptance moves `sent_to_provider` orders to `accepted`; provider
  rejection moves them to `cancelled` without clearing payment confirmation
  fields or reverting the order to `draft`.
- Admin-ingested provider production progress is implemented for accepted
  orders. Production start moves `accepted` orders to `in_production`; package
  ready moves `in_production` orders to `ready_for_pickup`. Minimal transition
  metadata is recorded in the admin audit log, and payment fields remain
  unchanged.
- Admin-ingested shipment is implemented for ready-for-pickup orders. Carrier
  QR pickup scans and authorized fallback events move `ready_for_pickup` orders
  to `shipped`. Minimal transition metadata is recorded in the admin audit log,
  and payment fields remain unchanged.
- Admin-ingested delivery confirmation is implemented for shipped orders.
  Trusted delivery confirmation events move `shipped` orders to `delivered`.
  Minimal transition metadata is recorded in the admin audit log, and payment
  fields remain unchanged.
- Paid-order cancellation request flow is implemented. Owning authenticated
  customers can request cancellation from `confirmed`, `accepted`, or
  `in_production`; admins can approve requests to move orders to `cancelled`
  or reject them back to the stored prior paid state. Payment confirmation and
  provider fulfillment history remain unchanged.
- Authenticated customer Order listing is implemented with strict owner-scoped
  pagination and a dedicated customer-safe summary projection.
- Authenticated customer Order detail is implemented with owner-scoped
  persisted Order and immutable OrderItem snapshot projection.

## Customer Order List

`GET /api/v1/orders` requires the existing bearer authentication dependency
and derives ownership only from the authenticated current user. Both the page
query and count query filter by that backend-derived `customer_id`; global
Order rows are never loaded and filtered in application code.

The endpoint accepts only `page` and `page_size`. `page` defaults to `1` and
must be at least `1`. `page_size` defaults to `20` and must be between `1` and
`100`. Every other query parameter is rejected with HTTP 422
`unsupported_query_parameter` and sorted unsupported parameter names before
Order list or count work begins.

Results are ordered by `created_at DESC, id DESC`. Responses use the dedicated
`OrderSummaryRead`, `OrderListMeta`, and `OrderListResponse` schemas:

```json
{
  "data": [
    {
      "id": 42,
      "status": "confirmed",
      "currency": "COP",
      "total_amount": "85000.00",
      "created_at": "2026-07-21T12:00:00Z",
      "updated_at": "2026-07-21T12:05:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_items": 1,
    "total_pages": 1
  }
}
```

`total_pages` is the ceiling of `total_items / page_size`, or `0` when the
owner has no Orders. A page beyond the final result returns an empty `data`
array while preserving owner-scoped totals.

Each summary exposes exactly `id`, `status`, `currency`, `total_amount`,
`created_at`, and `updated_at`. Currency and total are read from the persisted
backend-owned Order snapshot and are never recomputed from mutable catalog,
pricing, or OrderItem state. The list query loads only these scalar summary
columns and does not eager-load or serialize customer, OrderItem, Payment,
provider, policy, cancellation provenance, audit, admin, or internal state.
List reads are deterministic for unchanged persistence and do not mutate Order
or related records.

## Customer Order Detail

`GET /api/v1/orders/{order_id}` requires the existing bearer authentication
dependency and returns one dedicated direct `OrderDetailRead` response. The
repository query filters by both `order_id` and the authenticated current
user's `customer_id`. Unknown and cross-customer ids return the same HTTP 404
`Order not found` response without revealing whether an Order exists.

The response exposes persisted customer-safe Order fields only:

```json
{
  "id": 42,
  "status": "confirmed",
  "currency": "COP",
  "subtotal_amount": "85000.00",
  "discount_amount": "0.00",
  "tax_amount": "0.00",
  "total_amount": "85000.00",
  "payment_verified_at": "2026-07-21T12:05:00Z",
  "provider_handoff_sent_at": null,
  "created_at": "2026-07-21T12:00:00Z",
  "updated_at": "2026-07-21T12:05:00Z",
  "items": [
    {
      "item_type": "product",
      "display_name": "Emergency exit sign",
      "customer_safe_description": "Standard exit signage.",
      "selected_options": {},
      "quantity": 2,
      "unit_price_amount": "42500.00",
      "line_subtotal_amount": "85000.00",
      "line_discount_amount": "0.00",
      "line_tax_amount": "0.00",
      "line_total_amount": "85000.00",
      "currency": "COP"
    }
  ]
}
```

Items are ordered by `OrderItem.id ASC` and use only the persisted immutable
snapshot columns shown above. Detail reads do not join to or recalculate from
current Product, Kit, Template, Design, pricing, provider, or fixture state.
OrderItem ids, catalog foreign keys, ownership, cancellation provenance,
payment/provider references, policy versions, provider payloads/costs, audit,
admin, and internal fields are not exposed.

The endpoint accepts no query parameters. Authentication is evaluated first,
so missing or invalid authentication returns HTTP 401 even when query
parameters are supplied. Authenticated requests with any query parameter
return HTTP 422 `unsupported_query_parameter` with sorted names before Order
detail repository work. Reads are deterministic for unchanged persistence and
do not mutate Order, OrderItem, Payment, catalog, provider, audit, or other
state.

The existing `GET /api/v1/orders/{order_id}/status` response remains unchanged.
Its broader catalog-id and cancellation-provenance fields are separate
contract-minimization debt and are not part of this detail response.


## Related Endpoints

- POST /api/v1/orders
- GET /api/v1/orders
- GET /api/v1/orders/{order_id}
- GET /api/v1/orders/{order_id}/status

See docs/api/endpoint-structure.md.

## Child Issues

- #29 Define order status lifecycle
- #30 Create Order and OrderItem models, migrations, and tests
- #31 Create POST order endpoint with tests
- #32 Create GET order status endpoint with tests
- #33 Create GET order status endpoint with tests
- #35 Prepare paid-order provider adapter handoff payload
- #61 Send order to provider
- #188 Add customer order list endpoint
- #189 Add full customer order detail endpoint

## Future Issues

- Future issue required: add idempotency/retry protection for order creation

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
