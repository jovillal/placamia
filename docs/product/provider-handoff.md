# Provider Handoff

## Goal

Ensure orders are transmitted clearly for manufacturing.

The MVP follows Path A: this handoff happens through the provider adapter
boundary only after verified customer payment. The assigned manufacturing
provider accepts or rejects a paid order through the adapter boundary after
handoff; it does not provide a pre-checkout quote confirmation for
direct-checkout MVP items.

Partner-specific validation findings may name the provider that supplied them,
but handoff data, status transitions, and authorization rules must remain
provider-neutral.

---

## Order Payload Requirements

The paid-order handoff payload is provider-neutral and generated only from
persisted backend data after verified customer payment and confirmed order
state. It must never forward raw frontend payloads or let the frontend choose
or spoof the assigned provider.

Required now:

- order identifier
- backend-assigned provider identifier
- handoff correlation identifiers, including attempt id and idempotency key
- order item identifiers
- item type and persisted product, kit, template, or design references
- display name and customer-safe description snapshots
- quantities
- backend-validated selected options such as material, size, finish, and
  template/customization values when captured
- persisted provider payload snapshot data needed for manufacturing

Optional now:

- QR or shipment reference when the carrier mechanism is available and
  persisted
- customer-safe production notes when a future persisted field exists

Deferred until modeled and persisted:

- delivery recipient name
- delivery address
- delivery phone
- delivery email
- delivery instructions

Deferred delivery/contact fields must not be invented from frontend payloads
during handoff. Later implementation must persist and test them before making
them required.

The payload must exclude sensitive or unnecessary fields, including payment
provider references, payment timestamps, provider cost, raw provider pricing
data, raw frontend data, internal audit fields, secrets, tokens, and
customer-sensitive data not required for fulfillment.

Provider acceptance or rejection is an adapter response after handoff. It is
not payment confirmation and must not alter payment verification status.

---

## Order Status Lifecycle

- draft
- confirmed
- sent_to_provider
- accepted
- in_production
- ready_for_pickup
- shipped
- delivered
- cancelled
- cancellation_requested

---

## Risks

- ambiguous specifications
- mismatched catalog vs production capability
- duplicate provider handoff retries
- QR pickup mechanism unavailable or inconsistent
- accounting, invoicing, payout, or SLA rules automated before legal review

---

## Mitigation

- strict schema for orders
- validation before submission
- manual fallback if needed
- handoff generated only from persisted backend data
- backend-owned provider assignment
- stable handoff idempotency key for retries
- handoff, status, and acceptance/rejection recorded through the provider
  adapter boundary
- idempotent provider transmission where possible
- operator shipment fallback until QR pickup is technically validated

---

## Initial Approach

- simple structured paid-order payload
- no complex provider integration yet
- provider acceptance/rejection can be manual or API later, but must be
  recorded through the provider adapter boundary
- QR pickup scan is preferred for shipment; authorized operator update is the
  fallback until carrier validation is complete
- customer invoicing, provider invoicing, provider payout, and SLA consequences
  must be documented before automation
