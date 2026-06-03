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

Each order must include:

- product identifiers
- quantities
- material
- size
- design specifications
- delivery address
- order identifier
- QR or shipment reference when the carrier mechanism is available

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
