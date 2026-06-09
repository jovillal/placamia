# Checkout Tasks

## Purpose

Track executable checkout work for the Path A MVP.

Path A means backend pricing and direct-checkout eligibility are validated
before payment. Provider acceptance or rejection happens after verified customer
payment as part of paid-order handoff.

## Source Documents

- `docs/flows/checkout-flow.md`
- `docs/flows/provider-fulfillment-flow.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/planning/provider.md`
- `docs/planning/provider-adapter-contract.md`
- `docs/planning/security.md`
- `docs/validation/pricing-model.md`
- `docs/validation/availability-model.md`
- `docs/validation/commercial-model.md`
- `docs/research/legal-business-questions.md`

## Current Baseline

Known planning issues:

- pricing model/service/endpoint are planned but not Path A-complete
- checkout implementation is on the critical path after provider adapter
  foundation, catalog eligibility, and pricing
- direct-checkout eligibility boundary (#100), local/mock adapter fixtures
  (#108), product eligibility fields (#109), and kit eligibility behavior
  (#110) should be settled before checkout depends on catalog purchasability
- order lifecycle needs `ready_for_pickup` and `cancellation_requested`
- payment webhook work must distinguish payment-provider confirmation from
  manufacturing-provider acceptance
- provider handoff must be generated only after verified payment
- provider adapter boundary and local/mock adapter are needed before checkout
  implementation depends on provider behavior
- cancellation/refund terms can start with backend-owned placeholder policy and
  must be updated from legal/business validation before production checkout

## Provider and Legal Validation Tasks

These run in parallel with backend implementation. Checkout implementation
depends on the provider adapter boundary and local/mock adapter, not on a real
provider integration or completed partner validation.

Answers may name the specific validation partner that provided them, but policy
and implementation must be recorded in provider-neutral terms. Final production
checkout terms must be updated from legal/business validation before launch.

- Confirm cancellation/refund/warranty terms shown before payment.
- Confirm what happens when the assigned provider rejects a paid order.
- Confirm whether provider payout happens at dispatch, delivery, invoice
  receipt, or another milestone.
- Confirm who invoices the customer and when providers invoice PlacamIA.
- Confirm SLA consequences before automating penalties or compensation.
- Confirm QR pickup feasibility or define authorized operator fallback.

## Implementation Slices

### 1. Pricing Rule Foundation

Implement backend-owned pricing rules for direct-checkout items using provider
cost/capability inputs from the provider adapter boundary.

Related issues:

- #26 Define Path A pricing rule model and service contracts
- #27 Implement Path A pricing preview service with unit tests
- #28 Create POST pricing preview endpoint for Path A direct checkout

Acceptance criteria:

- pricing can calculate products, kits, and designs
- pricing can use local/mock adapter cost inputs without a real provider
  integration
- invalid options are rejected
- inactive, unavailable, manual-quote-only, or non-priceable items are rejected
- frontend price, subtotal, total, availability, and discounts are ignored
- tests cover valid pricing and security-sensitive rejection paths

### 2. Checkout Eligibility Gate

Validate direct-checkout eligibility immediately before draft order/payment
initialization using backend catalog state and provider adapter boundary
responses.

Related issues:

- #100 Define direct-checkout eligibility boundary and public catalog contract
- #108 Implement local/mock provider adapter availability fixtures
- #109 Add product listing and detail eligibility fields
- #110 Add kit direct-checkout eligibility behavior
- #101 Implement checkout eligibility gate and terms acknowledgement

Acceptance criteria:

- checkout uses the local/mock adapter when no real provider adapter exists
- checkout rejects stale or unavailable catalog state
- checkout rejects unsupported design/customization values
- checkout requires backend-calculated pricing
- rejected checkout creates no order/payment records
- tests cover frontend tampering and no-mutation behavior

### 3. Cancellation and Refund Terms Acknowledgement

Capture that the customer saw and accepted the applicable terms before payment.
Initial implementation may use a backend-owned placeholder terms policy for
local/mock adapter development; production terms must be updated from
commercial/legal validation before launch.

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

- payment lifecycle/domain validation defines the allowed payment statuses
- frontend payment confirmation alone cannot mark an order paid
- invalid or missing webhook signature is rejected
- replayed webhook does not duplicate state changes
- failed payment does not confirm order
- provider handoff is not triggered by invalid, failed, or replayed payment
- provider acceptance/rejection is not treated as payment confirmation

### 6. Paid-Order Provider Handoff

Send a complete paid-order payload to the assigned provider after verified
payment through the provider adapter boundary. The local/mock adapter is the
first implementation target.

Acceptance criteria:

- payload is generated from persisted order/order item/design data
- raw frontend payload is never forwarded
- handoff works with the local/mock adapter without a real provider integration
- handoff is idempotent where possible
- failed transmission does not corrupt order state
- provider acceptance/rejection updates order state

### 7. Fulfillment and Shipment Status

Implement fulfillment statuses through `ready_for_pickup`, `shipped`, and
`delivered` using provider adapter status/decision responses and authorized
operator fallback where documented.

Acceptance criteria:

- local/mock adapter can simulate accepted, rejected, in production, ready for
  pickup, and delivered states
- Provider/operator status mutations follow authorization rules when real
  provider/operator integrations are introduced
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
