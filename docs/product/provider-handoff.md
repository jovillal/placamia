# Provider Handoff (Relieves de Colombia)

## Goal

Ensure orders are transmitted clearly for manufacturing.

---

## Order Payload Requirements

Each order must include:

- product identifiers
- quantities
- material
- size
- design specifications
- delivery address

---

## Order Status Lifecycle

- draft
- confirmed
- sent_to_provider
- accepted
- in_production
- shipped
- delivered
- cancelled

---

## Risks

- ambiguous specifications
- mismatched catalog vs production capability

---

## Mitigation

- strict schema for orders
- validation before submission
- manual fallback if needed

---

## Initial Approach

- simple structured payload
- no complex integration yet
- can be manual or API later