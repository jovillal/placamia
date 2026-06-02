# Provider Integration Options

(Discovery Phase / Non-Canonical)

## MVP Status

The MVP decision is Path A: direct checkout for fully parametrizable,
backend-priceable products and kits, with paid-order handoff to Relieves after
verified customer payment.

This document captures integration options through that lens. RFQ or
provider-confirmed checkout remains future research for manual/custom work.

## Selected MVP Integration Shape

```text
Weekly availability update
    ->
Direct checkout for eligible catalog items
    ->
Verified customer payment
    ->
Paid-order handoff to Relieves
    ->
Relieves acceptance/rejection
    ->
Production, pickup, shipment, delivery
```

## Core Assumption

PlacamIA should not try to fix or replace Relieves' internal operations.

Instead, PlacamIA should capture only what Relieves can reliably provide for
the MVP:

- which products can be sold directly
- which products require manual quote review and must stay out of checkout
- current soft availability
- stable pricing parameters
- production and pickup timing
- fulfillment status after paid handoff

## Path A Integration Flows

### 1. Catalog Eligibility

Answers:

- can this product or kit be sold through direct checkout?
- are all selected options valid?
- can the backend calculate the final price?
- does current availability allow sale?

MVP recommendation:

- keep the initial catalog small
- mark products as direct-checkout eligible only after Relieves validates
  pricing and production assumptions
- exclude manual-quote/custom products from checkout

### 2. Availability Communication

Answers:

- can Relieves support this product this week?
- is it available, made-to-order, temporarily unavailable, or manual quote only?
- should PlacamIA hide it from checkout?

MVP recommendation:

- use weekly form/manual update
- avoid exact inventory counts
- store soft availability at product or product-family level
- allow configuration-level overrides only after the product rules require it

Initial availability classes:

- available
- made_to_order_parametrizable
- temporarily_unavailable
- manual_quote_required
- outsourced_not_mvp_direct

### 3. Pricing Rules

Answers:

- what variables determine Relieves' base price?
- what combinations are valid?
- how does PlacamIA apply margin?
- when must a product leave direct checkout because pricing is unstable?

MVP recommendation:

- backend-owned pricing table
- deterministic rules by material, size, quantity, finish, and other agreed
  variables
- no frontend-provided totals
- no manual discounts unless represented by explicit backend rules

### 4. Paid-Order Handoff

Answers:

- what does Relieves need to manufacture without customer contact?
- how is the handoff made traceable?
- how are retries made safe?

MVP recommendation:

- structured payload from persisted Order, OrderItems, Design, and delivery
  data
- simple email/manual/API handoff depending on operational readiness
- idempotency key or unique order reference for retries
- no raw frontend payload forwarding

### 5. Fulfillment Status

Answers:

- has Relieves accepted or rejected the paid order?
- is production underway?
- is the package ready for pickup?
- has the carrier picked it up?
- has it been delivered?

MVP recommendation:

- start with manual or email-confirmed status updates if needed
- use QR pickup scan as preferred shipped trigger once carrier validation is
  complete
- use authorized operator fallback until QR is reliable

## Versioned Options

### V1: Manual Operations

Capabilities:

- weekly availability form
- internal/operator catalog availability update
- backend direct-checkout pricing
- paid-order email or structured handoff to Relieves
- operator-entered provider acceptance/rejection/status if needed
- QR or operator fallback for shipment event

This is the recommended MVP integration level.

### V1.5: Secure Provider Links

Possible capabilities:

- secure link for Relieves to accept/reject paid orders
- secure link to update production status
- expiring package/QR download or confirmation link
- audit trail for provider actions

### V2: Provider Dashboard or Uploads

Possible capabilities:

- provider dashboard
- CSV availability upload
- provider-managed status updates
- provider terms acceptance
- richer audit trail

### V3: API Integration

Possible capabilities:

- provider API
- automated availability sync
- automated status updates
- exact inventory only if Relieves has a reliable inventory process

## Future RFQ Path

RFQ becomes relevant when a product cannot satisfy Path A:

- price cannot be calculated deterministically
- Relieves must review feasibility before payment
- custom files determine scope
- quantities require site-specific expert judgment
- outsourcing creates uncertain price or lead time

If PlacamIA later chooses that path, update canonical flow and planning docs
before implementation. Do not implement RFQ behavior from this research alone.

## Open Questions

1. Which products are direct-checkout eligible?
2. Which products are manual-quote-only?
3. What availability states can Relieves report weekly?
4. Who owns weekly availability updates?
5. What variables define the pricing table?
6. Which material/size/finish combinations are invalid?
7. What is the SLA for accepting or rejecting a paid order?
8. What production and pickup timelines can PlacamIA safely communicate?
9. Can the selected carrier scan QR codes at pickup?
10. What is the fallback shipment update process?
11. What events should notify customers?
12. What events should notify Relieves?
13. What legal/accounting policy controls provider payout and invoicing?

## Recommendation

Start with the smallest operationally trustworthy integration:

```text
Weekly availability
    ->
Direct checkout
    ->
Paid-order handoff
    ->
Manual/traceable fulfillment updates
```

Build provider self-service only after the direct-checkout flow proves demand
and Relieves' operational update cadence is clear.
