# Checkout Tasks

## Purpose

Track executable checkout work for the Path A MVP.

Path A means backend pricing and direct-checkout eligibility are validated
before payment. Relieves acceptance or rejection happens after verified customer
payment as part of paid-order handoff.

## Source Documents

- `docs/flows/checkout-flow.md`
- `docs/flows/provider-fulfillment-flow.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/planning/provider.md`
- `docs/planning/security.md`
- `docs/research/legal-business-questions.md`

## Current Baseline

Known planning issues:

- pricing model/service/endpoint are planned but not Path A-complete
- order lifecycle needs `ready_for_pickup` and `cancellation_requested`
- payment webhook work must distinguish payment-provider confirmation from
  Relieves acceptance
- provider handoff must be generated only after verified payment
- cancellation/refund terms need legal/business validation before real checkout

## Relieves and Legal Validation Tasks

These should be closed before production checkout depends on them.

- Confirm cancellation/refund/warranty terms shown before payment.
- Confirm what happens when Relieves rejects a paid order.
- Confirm whether provider payout happens at dispatch, delivery, invoice
  receipt, or another milestone.
- Confirm who invoices the customer and when Relieves invoices PlacamIA.
- Confirm SLA consequences before automating penalties or compensation.
- Confirm QR pickup feasibility or define authorized operator fallback.

## Implementation Slices

### 1. Pricing Rule Foundation

Implement backend-owned pricing rules for direct-checkout items.

Acceptance criteria:

- pricing can calculate products, kits, and designs
- invalid options are rejected
- inactive, unavailable, manual-quote-only, or non-priceable items are rejected
- frontend price, subtotal, total, availability, and discounts are ignored
- tests cover valid pricing and security-sensitive rejection paths

### 2. Checkout Eligibility Gate

Validate direct-checkout eligibility immediately before draft order/payment
initialization.

Acceptance criteria:

- checkout rejects stale or unavailable catalog state
- checkout rejects unsupported design/customization values
- checkout requires backend-calculated pricing
- rejected checkout creates no order/payment records
- tests cover frontend tampering and no-mutation behavior

### 3. Cancellation and Refund Terms Acknowledgement

Capture that the customer saw and accepted the applicable terms before payment.

Acceptance criteria:

- terms are backend-selected, not frontend-authored
- checkout cannot proceed without terms acknowledgement
- acknowledged terms are persisted or referenced for the order
- tests cover missing or forged acknowledgement

### 4. Order Creation

Create draft orders from backend-validated checkout state.

Acceptance criteria:

- order items are built from persisted/backend-validated data
- totals use backend pricing only
- unauthenticated access is rejected where required
- user cannot create or view another user's order
- rejected order creation does not mutate the database

### 5. Payment Initialization and Webhook Verification

Confirm orders only through verified payment-provider events.

Acceptance criteria:

- frontend payment confirmation alone cannot mark an order paid
- invalid or missing webhook signature is rejected
- replayed webhook does not duplicate state changes
- failed payment does not confirm order
- provider handoff is not triggered by invalid, failed, or replayed payment

### 6. Paid-Order Provider Handoff

Send a complete paid-order payload to Relieves after verified payment.

Acceptance criteria:

- payload is generated from persisted order/order item/design data
- raw frontend payload is never forwarded
- handoff is idempotent where possible
- failed transmission does not corrupt order state
- provider acceptance/rejection updates order state

### 7. Fulfillment and Shipment Status

Implement fulfillment statuses through `ready_for_pickup`, `shipped`, and
`delivered`.

Acceptance criteria:

- Relieves/operator can mark accepted, rejected, in production, ready for
  pickup, and delivered according to authorization rules
- `ready_for_pickup -> shipped` requires valid QR pickup event or authorized
  operator fallback
- status endpoint returns customer-safe data only
- tests cover unauthorized status changes and cross-user access

### 8. Cancellation Request Flow

Allow paid customers to request cancellation without automatically cancelling
the order.

Acceptance criteria:

- request moves order to `cancellation_requested`
- approval/rejection is authorized and audited
- customer cannot directly force `cancelled`
- state returns to the correct prior state if request is rejected
- tests cover no unauthorized mutation

## Security Tests

Checkout issues must include tests for:

- frontend-supplied price ignored
- frontend-supplied availability ignored
- inactive/unavailable/manual-quote-only items rejected
- unauthenticated protected access rejected
- user cannot access another user's orders
- invalid payment webhook rejected without mutation
- provider handoff requires verified payment
- duplicate handoff/status events do not duplicate state changes

## Out of Scope

- RFQ/provider-confirmed checkout before payment
- partial payments or deposits
- storing payment card data
- provider payout automation
- invoice automation
- SLA penalty automation
- carrier integration beyond validated QR/fallback event capture
