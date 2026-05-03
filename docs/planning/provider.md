# Provider Integration

## Goal

Transmit validated orders to the manufacturing provider (Relieves de Colombia)
in a clear, structured, and reliable way.

This is a critical boundary between PlacamIA and real-world production.

## Core Principles

- Provider payloads must be generated from persisted backend data
- Do not forward raw frontend input
- Payload must be complete and unambiguous
- Transmission must be reliable and traceable

See `docs/product/provider-handoff.md`

## Flow

1. Order is confirmed (after payment)
2. Backend prepares export payload from Order
3. Backend sends payload to provider
4. Provider acknowledges or rejects
5. Backend updates order status accordingly

## Scope

- Provider payload transmission
- Provider response handling
- Order status updates based on provider feedback
- Error handling and retries

## Related Concepts

- Order
- OrderItem
- Design
- ProductionJob (future)

See `docs/architecture/domain-model.md`

## Child Issues

- Send order to provider
- define structured provider handoff payload

## Missing Issues

- Send order to provider (API/email/manual)
- Handle provider response (accepted/rejected)
- Implement retry logic for failed transmissions
- Add logging for provider communication
- Add validation for payload completeness
- Add tests ensuring payload is built from persisted data only

## Constraints

- Do not send incomplete orders
- Do not send unvalidated data
- Do not allow frontend to influence provider payload directly
- Provider communication must be idempotent where possible

## Security Considerations

- Ensure payload contains only necessary data
- Do not expose internal fields
- Validate all outgoing data
- Log transmission events without leaking sensitive data

## Testing Requirements

Provider integration must include tests for:

- correct payload generation from order data
- payload does not include frontend-only fields
- provider transmission success handling
- provider rejection handling
- retries do not duplicate state changes
- failed transmission does not corrupt order state

## Done When
- Orders can be transmitted to provider
- Payload structure is validated and consistent
- Provider responses are handled correctly
- Order status reflects provider state
- Tests cover success and failure scenarios