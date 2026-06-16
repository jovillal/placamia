# Provider Integration

## Goal

Define the provider adapter boundary that lets PlacamIA use manufacturing
providers without coupling core checkout, pricing, order, payment, or tracking
behavior to one provider-specific workflow.

This is a critical boundary between PlacamIA and real-world production.

The MVP follows Path A: the assigned provider receives a paid-order handoff only
after customer payment is verified. Provider acceptance or rejection happens
after payment; it is not a pre-checkout RFQ gate for fully parametrizable MVP
items.

Partner-specific validation findings may name the provider that supplied them,
but the system must be designed so additional manufacturing providers can be
onboarded later without changing the customer checkout flow.

## Core Principles

- PlacamIA core owns catalog, templates, designs, checkout, orders, payments,
  and customer tracking.
- Providers supply availability, provider cost/pricing inputs, fulfillment
  capability, lead time, paid-order handoff response, and acceptance/rejection
  through a normalized adapter contract.
- Provider assignment must be backend-owned.
- Provider payloads must be generated from persisted backend data.
- Raw frontend input must never be forwarded directly to a provider.
- Provider payloads must use backend-owned provider assignment and never accept
  provider selection from frontend input.
- Backend pricing remains the source of truth for customer-facing totals.
- The paid order is the production trigger.
- Provider communication must be reliable, traceable, and idempotent where
  possible.
- Start inside the modular monolith; do not introduce microservices for MVP
  provider integration.

See `docs/product/provider-handoff.md` and
`docs/flows/provider-fulfillment-flow.md`.

Detailed adapter method and result contracts live in
`docs/planning/provider-adapter-contract.md`.

Related validation docs:

- `docs/validation/provider-onboarding-checklist.md`
- `docs/validation/product-classification.md`
- `docs/validation/availability-model.md`
- `docs/validation/commercial-model.md`

## Provider Adapter Strategy

The first implementation target is a deterministic local/mock provider adapter.
This lets backend work continue before a real provider integration is validated.

Real-provider integrations must initially be implemented as adapters inside the
modular monolith. A real provider adapter may be extracted into an external
service only after the monolith implementation proves that operational
complexity, ownership boundaries, or scaling constraints justify the move.

Adapter implementations may differ, but the PlacamIA core must call them
through the same contract.

Current state:

- The provider adapter boundary and deterministic local/mock adapter are
  implemented in the modular monolith.
- Local/mock availability, provider cost/capability input, direct-checkout
  eligibility, lead time, paid-order handoff, status lookup, and
  acceptance/rejection fixture behavior are available for backend tests.
- Paid-order handoff payload preparation and transmission to the local/mock
  adapter are implemented after verified payment and confirmed order state.
- Provider acceptance/rejection lifecycle persistence is implemented for orders
  already sent through the provider adapter boundary. Provider rejection leaves
  payment confirmation fields intact and moves the order to `cancelled` through
  the lifecycle validator.
- Admin-ingested provider production progress is implemented for the MVP. The
  existing admin authorization and audit-log pattern records production start
  and package-ready events without introducing provider-specific auth or an
  operator role.
- Real-provider adapters, provider status reconciliation, shipment updates, and
  durable provider production event ledgers remain future work.

## Provider Adapter Contract

Detailed contract source: `docs/planning/provider-adapter-contract.md`.

The provider adapter boundary is the provider-facing contract for:

- availability
- provider cost/capability inputs
- direct-checkout eligibility
- lead time estimates
- paid-order handoff after verified payment
- handoff status reconciliation
- provider acceptance/rejection recording

The first implementation must be a deterministic local/mock adapter. Validation
partner findings may later update local/mock fixtures and seed data, but they
must not block implementation of the adapter boundary.

## Flow

1. Order is confirmed after verified customer payment
2. Backend prepares paid-order payload from Order, OrderItems, and Design data
3. Backend calls the provider adapter for paid-order handoff
4. Provider adapter returns handoff status and provider reference
5. Provider accepts or rejects the paid order through the adapter boundary
6. Provider manufactures accepted orders
7. Provider prepares the package and attaches the order QR when available
8. Carrier pickup scan, or operator fallback, marks the order shipped
9. Backend updates order status and customer notifications accordingly

## Scope

- Provider adapter boundary
- Local/mock provider adapter
- Provider payload transmission through the adapter
- Backend-owned provider assignment for paid-order handoff
- Provider response and decision handling
- Order status updates based on provider feedback
- Error handling and retries
- Shipment event handling for QR pickup scan or operator fallback

## Related Concepts

- Provider = configured manufacturing partner that can receive paid-order
  handoffs
- Provider assignment = backend-owned decision about which configured provider
  will fulfill a direct-checkout order item or order
- Provider availability = provider-specific operational signal for the current
  catalog period
- Order
- OrderItem
- Design
- Shipment
- ProductionJob (future)

See `docs/architecture/domain-model.md`

## Child Issues

- #34 Define structured provider handoff payload
- #35 Prepare paid-order provider adapter handoff payload
- #61 Send order to provider

## Future Issues

- Future issue required: implement real-provider adapter integrations inside
  the modular monolith after provider validation
- Future issue required: add admin/operator retry endpoint for failed provider
  transmissions if manual retry is needed operationally
- Future issue required: implement provider handoff status reconciliation
  through the adapter
- Future issue required: validate QR pickup scan or define operator shipment
  fallback before implementing automated shipment updates
- Future issue required: document customer invoicing, provider invoicing,
  PlacamIA payment to providers, and SLA consequences before automating them

## Constraints

- Do not send incomplete orders
- Do not send unvalidated data
- Do not allow frontend to influence provider payload directly
- Do not allow frontend to choose or spoof the assigned provider
- Do not let frontend-supplied provider price, availability, eligibility, or
  lead time influence backend decisions
- Provider communication must be idempotent where possible
- Do not send provider handoff before verified payment
- Do not use provider acceptance as a checkout prerequisite for MVP direct
  checkout items
- Do not implement real-provider integrations outside the modular monolith
  unless a future architecture decision explicitly approves extraction
- Do not automate accounting, payout, or SLA consequences until legal and
  accounting policy is documented

## Security Considerations

- Ensure payload contains only necessary data
- Do not expose internal fields
- Validate all outgoing data
- Log transmission events without leaking sensitive data
- Retried handoffs must not duplicate provider orders
- Provider rejection must not expose internal customer or payment details
- Adapter responses must be validated before mutating order state

## Testing Requirements

Provider integration must include tests for:

- local/mock adapter success and rejection cases
- availability, pricing input, eligibility, and lead time adapter behavior
- frontend provider, price, availability, and lead time spoofing rejection
- correct payload generation from order data
- payload does not include frontend-only fields
- provider transmission success handling
- provider rejection handling
- retries do not duplicate state changes
- failed transmission does not corrupt order state
- handoff is not attempted before verified payment
- shipment updates require a valid QR scan event or authorized operator fallback

## Done When
- Provider adapter boundary is documented and implemented in the monolith
- Local/mock provider adapter supports Path A backend development
- Orders can be transmitted through the provider adapter
- Payload structure is validated and consistent
- Provider handoff success updates order state to `sent_to_provider`
- Provider acceptance/rejection and status responses are handled correctly
- QR shipment trigger or documented operator fallback is implemented safely
- Tests cover success and failure scenarios
