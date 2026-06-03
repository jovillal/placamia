# Provider Adapter Contract

## Goal

Define the normalized provider adapter contract that lets PlacamIA use one or
many manufacturing providers without coupling catalog, pricing, checkout,
orders, payments, or tracking to provider-specific workflows.

The contract starts inside the modular monolith. Real-provider integrations
must be implemented as monolith adapters first; extracting an adapter into an
external service is future architecture work only if operational evidence
justifies it.

## Core Rules

- PlacamIA core owns catalog, templates, designs, checkout, orders, payments,
  customer-facing pricing, and customer tracking.
- Providers supply availability, provider cost/capability inputs, fulfillment
  capability, lead time, paid-order handoff response, handoff status, and
  acceptance/rejection through this adapter contract.
- Provider assignment is backend-owned.
- The frontend must not choose, spoof, or override provider assignment,
  provider cost, availability, eligibility, lead time, handoff status, or
  acceptance/rejection.
- Paid-order handoff must happen only after verified payment.
- Provider acceptance is not a checkout prerequisite for MVP direct-checkout
  items.
- Adapter responses must be validated before mutating order state.

## Conceptual Interface

```text
ProviderAdapter
  check_availability(request) -> AvailabilityResult
  quote_pricing(request) -> ProviderPricingResult
  check_direct_checkout_eligibility(request) -> EligibilityResult
  estimate_lead_time(request) -> LeadTimeResult
  handoff_paid_order(request) -> HandoffResult
  get_handoff_status(provider_reference) -> ProviderStatusResult
  record_acceptance(provider_reference, decision) -> AcceptanceResult
```

These names define the conceptual contract. The implementation may use Python
classes, protocols, or explicit service functions as long as PlacamIA core
depends on this boundary rather than provider-specific workflows.

## Operations

### Availability Check

```text
check_availability(request) -> AvailabilityResult
```

Purpose: determine whether a provider can currently support a product, kit, or
design configuration.

Inputs:

- product, kit, or design configuration identifier
- material, size, finish, quantity, and other backend-validated options
- assigned provider identifier

Outputs:

- availability state
- reason code for unavailable, manual-quote-only, unsupported, or temporarily
  unavailable states
- effective date or catalog period when applicable

Rules:

- Availability is backend-owned and must not be accepted from frontend claims.
- Availability is a soft operational signal, not exact inventory reservation.

### Pricing Quote

```text
quote_pricing(request) -> ProviderPricingResult
```

Purpose: obtain provider cost/capability inputs needed by backend pricing.

Inputs:

- backend-validated product, kit, or design configuration
- quantity
- assigned provider identifier

Outputs:

- provider cost input or base price input
- supported adjustments or rejection reason
- quote reference for traceability when applicable

Rules:

- `quote_pricing` must not become a frontend price or checkout total.
- Provider pricing output is provider-owned base cost, capability, adjustment,
  or rejection data only.
- PlacamIA backend calculates final customer price, margin, taxes/fees when
  applicable, discounts, and checkout total.
- PlacamIA backend must ignore or reject frontend-supplied prices, provider
  costs, subtotals, discounts, taxes, fees, and totals.

### Direct-Checkout Eligibility

```text
check_direct_checkout_eligibility(request) -> EligibilityResult
```

Purpose: decide whether a product, kit, or design configuration can proceed
through Path A checkout.

Inputs:

- backend catalog state
- backend-validated customization/options
- provider availability result
- provider pricing/capability result

Outputs:

- eligible or not eligible
- reason code
- assigned provider identifier

Rules:

- Manual-quote-only, unavailable, inactive, unsupported, or non-priceable items
  must not enter direct checkout.
- The frontend must not be able to choose, spoof, or override provider
  assignment or eligibility.

### Lead Time Estimate

```text
estimate_lead_time(request) -> LeadTimeResult
```

Purpose: provide a customer-safe estimate for fulfillment expectations.

Inputs:

- eligible product, kit, or design configuration
- quantity
- assigned provider identifier

Outputs:

- estimated production lead time
- estimated pickup/dispatch lead time when available
- uncertainty or fallback reason when exact values are not available

Rules:

- Lead time is an estimate, not an SLA promise unless commercial validation
  explicitly documents that commitment.

### Paid-Order Handoff

```text
handoff_paid_order(request) -> HandoffResult
```

Purpose: send a verified paid order to the assigned provider for fulfillment.

Inputs:

- persisted Order
- persisted OrderItems
- persisted Design data when applicable
- delivery and shipment reference data required for fulfillment

Outputs:

- provider handoff reference
- handoff status
- retry/idempotency key or equivalent trace reference

Rules:

- Handoff happens only after verified payment.
- Payload must be generated from persisted backend data.
- Failed transmission must not corrupt order state.
- Retried handoffs must not duplicate provider orders.

### Handoff Status

```text
get_handoff_status(provider_reference) -> ProviderStatusResult
```

Purpose: retrieve or reconcile the provider-side status for a previously
handed-off paid order.

Inputs:

- provider handoff reference
- assigned provider identifier when needed for lookup

Outputs:

- provider status
- customer-safe mapped status when available
- provider timestamp or synchronization timestamp when applicable
- reason code when status cannot be retrieved

Rules:

- Handoff status must not be trusted until the adapter response is validated.
- Provider-specific statuses must be mapped to PlacamIA order lifecycle states
  before mutating customer-visible order state.
- Failed status checks must not corrupt order state.

### Provider Acceptance Or Rejection

```text
record_acceptance(provider_reference, decision) -> AcceptanceResult
```

Purpose: capture whether the assigned provider accepts or rejects a paid order
after handoff.

Inputs:

- provider handoff reference
- provider decision or local/mock fixture decision

Outputs:

- accepted or rejected
- reason code when rejected
- customer-safe status mapping

Rules:

- Provider acceptance is not a checkout prerequisite.
- Provider rejection must not expose internal customer, payment, or provider
  details.
- Order state updates must follow the canonical lifecycle in
  `docs/flows/main-flow.md`.

## Local/Mock Adapter Requirements

The first adapter implementation must be a deterministic local/mock adapter.

It must:

- run locally without network access
- return deterministic availability states
- return deterministic provider cost inputs
- return deterministic direct-checkout eligibility results
- return deterministic lead time estimates
- simulate paid-order handoff success, failure, retry, and idempotency behavior
- simulate provider handoff status responses
- simulate provider acceptance and rejection
- provide fixtures for unavailable, manual-quote-only, unsupported, and
  temporarily unavailable items
- support tests proving frontend-supplied provider, provider cost, price,
  availability, eligibility, lead time, handoff status, and acceptance/rejection
  are ignored or rejected

Validation partner findings may later update local/mock fixtures and seed data.
They must not block implementation of this contract.

## Related Docs

- `docs/planning/provider.md`
- `docs/planning/catalog.md`
- `docs/planning/kits.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/flows/provider-fulfillment-flow.md`
