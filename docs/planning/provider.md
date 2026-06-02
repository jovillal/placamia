# Provider Integration

## Goal

Transmit validated orders to the assigned manufacturing provider in a clear,
structured, and reliable way.

This is a critical boundary between PlacamIA and real-world production.

The MVP follows Path A: the assigned provider receives a paid-order handoff only
after customer payment is verified. Provider acceptance or rejection happens
after payment; it is not a pre-checkout RFQ gate for fully parametrizable MVP
items.

Partner-specific validation findings may name the provider that supplied them,
but the system must be designed so additional manufacturing providers can be
onboarded later without changing the customer checkout flow.

## Core Principles

- Provider payloads must be generated from persisted backend data
- Provider assignment must be backend-owned
- Do not forward raw frontend input
- Payload must be complete and unambiguous
- Transmission must be reliable and traceable
- The paid order is the production trigger
- Provider communication must be generated from persisted backend state

See `docs/product/provider-handoff.md` and
`docs/flows/provider-fulfillment-flow.md`.

Related validation docs:

- `docs/validation/provider-onboarding-checklist.md`
- `docs/validation/product-classification.md`
- `docs/validation/availability-model.md`
- `docs/validation/commercial-model.md`

## Flow

1. Order is confirmed after verified customer payment
2. Backend prepares paid-order payload from Order, OrderItems, and Design data
3. Backend sends the paid-order payload to the assigned provider
4. Provider accepts or rejects the paid order
5. Provider manufactures accepted orders
6. Provider prepares the package and attaches the order QR when available
7. Carrier pickup scan, or operator fallback, marks the order shipped
8. Backend updates order status and customer notifications accordingly

## Scope

- Provider payload transmission
- Backend-owned provider assignment for paid-order handoff
- Provider response handling
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

Related Orders milestone:

- #61 Send order to provider

## Future Issues

- Future issue required: handle provider response accepted/rejected states
- Future issue required: implement retry logic for failed transmissions
- Future issue required: add logging for provider communication
- Future issue required: add validation for payload completeness
- Future issue required: add tests ensuring payload is built from persisted data
  only
- Future issue required: validate QR pickup scan or define operator shipment
  fallback before implementing automated shipment updates
- Future issue required: document customer invoicing, provider invoicing,
  PlacamIA payment to providers, and SLA consequences before automating them

## Constraints

- Do not send incomplete orders
- Do not send unvalidated data
- Do not allow frontend to influence provider payload directly
- Do not allow frontend to choose or spoof the assigned provider
- Provider communication must be idempotent where possible
- Do not send provider handoff before verified payment
- Do not use provider acceptance as a checkout prerequisite for MVP direct
  checkout items
- Do not automate accounting, payout, or SLA consequences until legal and
  accounting policy is documented

## Security Considerations

- Ensure payload contains only necessary data
- Do not expose internal fields
- Validate all outgoing data
- Log transmission events without leaking sensitive data
- Retried handoffs must not duplicate provider orders
- Provider rejection must not expose internal customer or payment details

## Testing Requirements

Provider integration must include tests for:

- correct payload generation from order data
- payload does not include frontend-only fields
- provider transmission success handling
- provider rejection handling
- retries do not duplicate state changes
- failed transmission does not corrupt order state
- handoff is not attempted before verified payment
- shipment updates require a valid QR scan event or authorized operator fallback

## Done When
- Orders can be transmitted to provider
- Payload structure is validated and consistent
- Provider responses are handled correctly
- Order status reflects provider state
- QR shipment trigger or documented operator fallback is implemented safely
- Tests cover success and failure scenarios
