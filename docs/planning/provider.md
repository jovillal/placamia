# Provider Integration

## Goal

Transmit validated orders to the manufacturing provider (Relieves de Colombia)
in a clear, structured, and reliable way.

This is a critical boundary between PlacamIA and real-world production.

The MVP follows Path A: Relieves receives a paid-order handoff only after
customer payment is verified. Relieves acceptance or rejection happens after
payment; it is not a pre-checkout RFQ gate for fully parametrizable MVP items.

## Core Principles

- Provider payloads must be generated from persisted backend data
- Do not forward raw frontend input
- Payload must be complete and unambiguous
- Transmission must be reliable and traceable
- The paid order is the production trigger
- Provider communication must be generated from persisted backend state

See `docs/product/provider-handoff.md` and
`docs/flows/provider-fulfillment-flow.md`.

## Flow

1. Order is confirmed after verified customer payment
2. Backend prepares paid-order payload from Order, OrderItems, and Design data
3. Backend sends the paid-order payload to Relieves
4. Relieves accepts or rejects the paid order
5. Relieves manufactures accepted orders
6. Relieves prepares the package and attaches the order QR when available
7. Carrier pickup scan, or operator fallback, marks the order shipped
8. Backend updates order status and customer notifications accordingly

## Scope

- Provider payload transmission
- Provider response handling
- Order status updates based on provider feedback
- Error handling and retries
- Shipment event handling for QR pickup scan or operator fallback

## Related Concepts

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
- Future issue required: document customer invoicing, Relieves invoicing,
  PlacamIA payment to Relieves, and SLA consequences before automating them

## Constraints

- Do not send incomplete orders
- Do not send unvalidated data
- Do not allow frontend to influence provider payload directly
- Provider communication must be idempotent where possible
- Do not send provider handoff before verified payment
- Do not use Relieves acceptance as a checkout prerequisite for MVP direct
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
