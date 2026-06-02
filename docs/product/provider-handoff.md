# Provider Handoff (Relieves de Colombia)

## Goal

Ensure orders are transmitted clearly for manufacturing.

The MVP follows Path A: this handoff happens only after verified customer
payment. Relieves de Colombia accepts or rejects a paid order after handoff; it
does not provide a pre-checkout quote confirmation for direct-checkout MVP
items.

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
- idempotent provider transmission where possible
- operator shipment fallback until QR pickup is technically validated

---

## Initial Approach

- simple structured paid-order payload
- no complex provider integration yet
- provider acceptance/rejection can be manual or API later
- QR pickup scan is preferred for shipment; authorized operator update is the
  fallback until carrier validation is complete
- customer invoicing, Relieves invoicing, provider payout, and SLA consequences
  must be documented before automation
