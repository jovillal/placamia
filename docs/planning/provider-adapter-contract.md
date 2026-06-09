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

### Paid-Order Handoff Payload Contract

This contract defines the provider-neutral payload shape that later payload
builder and adapter work must implement. It is documentation-only until the
runtime builder is added.

Payload generation is allowed only when:

1. Payment is verified by the payment-provider confirmation path.
2. The Order status is `confirmed`.
3. The assigned provider id is already stored in backend-owned Order or
   OrderItem data.

Provider assignment is never accepted from frontend input. The payload must use
the backend-assigned provider identifier already persisted for the order or
item being handed off.

#### Source Of Truth

The payload must be generated from persisted backend records:

- `Order`: id, status, assigned provider id, created timestamp, and provider
  handoff fields when retrying.
- `OrderItem`: item type, catalog/design references, display name,
  customer-safe description, selected options, quantity, assigned provider id,
  and provider payload snapshot.
- `Design`: persisted design/template data only when an order item references a
  design and the data already exists.

The payload must not be recomputed from mutable catalog records, provider
fixtures, current pricing rules, or raw frontend request bodies.

#### Required Payload Sections

```text
PaidOrderHandoffPayload
  contract_version
  correlation
  eligibility
  provider_assignment
  order
  items[]
  delivery
  shipment
```

Required now:

- `contract_version`: stable payload contract version, initially
  `paid_order_handoff_v1`.
- `correlation.order_id`: persisted PlacamIA Order id.
- `correlation.handoff_attempt_id`: backend-generated trace id for this handoff
  attempt.
- `correlation.idempotency_key`: stable retry key for the same Order/provider
  handoff.
- `eligibility.payment_status`: must indicate verified payment according to the
  payment lifecycle.
- `eligibility.order_status`: must be `confirmed`.
- `provider_assignment.assigned_provider_id`: backend-owned provider id.
- `order.created_at`: persisted order creation timestamp.
- `items[].order_item_id`: persisted OrderItem id.
- `items[].item_type`: product, kit, or design.
- `items[].display_name`: immutable order item display snapshot.
- `items[].customer_safe_description`: immutable order item description
  snapshot when present.
- `items[].quantity`: persisted purchased quantity.
- `items[].selected_options`: persisted backend-validated options, such as
  material, size, finish, and template/customization values when captured.
- `items[].references`: persisted product, kit, template, and design ids when
  present.
- `items[].provider_payload_snapshot`: persisted manufacturing-safe snapshot
  data captured for handoff, excluding forbidden fields below.

Optional now:

- `items[].customer_notes`: customer-safe, backend-approved production notes
  only if a future persisted field exists.
- `shipment.qr_reference`: package or pickup QR reference when the QR mechanism
  has been validated and persisted.
- `shipment.carrier_reference`: carrier shipment reference when available.

Deferred/placeholders until modeled and persisted:

- `delivery.recipient_name`
- `delivery.address`
- `delivery.phone`
- `delivery.email`
- `delivery.delivery_instructions`
- `shipment.qr_reference` when the carrier QR mechanism is not yet validated
  or persisted

Deferred delivery/contact fields must not be invented from frontend payloads at
handoff time. Later implementation work must add persisted fields and tests
before making any deferred field required.

#### Correlation And Idempotency

The handoff payload, adapter response, fulfillment status updates, and
acceptance/rejection events must be traceable to the originating Order without
exposing sensitive internal or payment data.

Required correlation values:

- `order_id`: persisted Order id.
- `assigned_provider_id`: backend-owned provider id.
- `handoff_attempt_id`: backend-generated trace id for a single transmission
  attempt.
- `idempotency_key`: stable key reused for retries of the same Order/provider
  handoff. Recommended format: `order:{order_id}:provider:{assigned_provider_id}`.

Adapter responses must echo or return the idempotency key and include a
provider handoff reference when a provider-side order exists. Retried handoffs
with the same idempotency key must not create duplicate provider orders.

#### Forbidden Fields

The provider payload must not include:

- payment provider reference
- payment verification timestamp
- payment webhook payloads or signatures
- card data or payment method details
- provider cost
- raw provider pricing data
- customer-facing backend pricing totals, margins, discounts, taxes, or fees
- raw frontend request bodies
- frontend-only fields, including frontend provider assignment or provider
  acceptance/rejection claims
- internal audit fields
- authentication tokens, secrets, or environment values
- full customer-sensitive data not required for fulfillment

#### Provider Acceptance/Rejection Response Shape

Provider acceptance and rejection are adapter responses after handoff. They are
not payment confirmation and must never alter payment verification status.

```text
AcceptanceResult
  provider_reference
  accepted
  customer_safe_status
  reason_code
  idempotency_key
```

The response must be validated before mutating order state. Rejection reason
codes must be customer-safe or mapped to customer-safe equivalents before they
are exposed outside admin/operator workflows.

#### Later Test Plan

Later runtime implementation issues must add tests proving:

- payloads are built from persisted Order, OrderItem, and persisted Design
  data only
- raw frontend payloads and frontend provider assignment claims are not
  forwarded
- required fields are present
- deferred delivery/contact fields are not invented
- forbidden payment, provider-cost, raw pricing, audit, and secret fields are
  excluded
- handoff requires verified payment and confirmed Order state
- retries use a stable idempotency key and do not duplicate provider orders

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
