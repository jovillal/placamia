# PlacamIA Timeline

## Product Direction

The MVP follows Path A: direct checkout for fully parametrizable,
backend-priceable products and kits.

RFQ/provider-confirmed checkout remains future work for manual/custom products.

Current critical path:

1. Provider Adapter Foundation
2. Direct-Checkout Eligibility
3. Pricing
4. Checkout
5. Orders, Payments, and Provider Handoff

Current implementation checkpoint:

- Provider adapter contract and deterministic local/mock adapter are in place.
- Catalog, kit, pricing, checkout eligibility, draft order creation, and order
  status surfaces are implemented for Path A backend development.
- Order and OrderItem persistence now includes provider assignment, immutable
  pricing/snapshot data, payment verification fields, and provider handoff
  trace fields.
- Paid-order handoff payload preparation and provider adapter transmission are
  implemented through the local/mock adapter after verified payment.
- Payment model persistence, payment initialization, signed payment webhook
  processing, durable webhook replay protection, and order confirmation after
  verified payment are implemented for the Path A provider-neutral payment
  boundary.
- Provider acceptance/rejection lifecycle persistence, production status
  updates, QR shipment ingestion, delivery confirmation, and paid-order
  cancellation requests are implemented for the MVP domain-local path.
- The Path A MVP mobile screen map is documented in
  `docs/planning/mobile-placeholder.md`, including screen dependencies,
  deferred mobile behavior, and backend gaps for the Expo placeholder.
- Real-provider adapter integrations, provider status reconciliation, and
  carrier API integration remain future work.

Template and design concepts remain part of the domain, but standalone template
endpoint expansion is supporting work. It should not block provider adapter,
eligibility, pricing, or checkout implementation unless a specific critical-path
issue depends on it.

## Phase 0 — Completed Foundation

### Completed

- Repo structure
- AGENTS.md
- Pytest baseline
- FastAPI backend foundation
- Security architecture and testing docs
- Catalog/category/product foundations
- Template/design validation foundation as supporting infrastructure
- Kit model and listing foundation
- Path A flow/planning/research reconciliation

## Phase 1 — Provider Contract Foundation

Goal: define the provider adapter boundary that lets PlacamIA build Path A
backend behavior without depending on one validation partner.

The provider adapter starts inside the modular monolith. A real provider
adapter may become an external service later only if operational complexity
justifies that change.

### 1. Provider Adapter Contract

Define the normalized provider adapter contract for:

- availability check
- provider cost/pricing input
- direct-checkout eligibility
- lead time estimate
- paid-order handoff
- handoff status reconciliation
- provider acceptance/rejection recording

Outputs:

- conceptual `ProviderAdapter` interface
- request/response contracts for `AvailabilityResult`,
  `ProviderPricingResult`, `EligibilityResult`, `LeadTimeResult`,
  `HandoffResult`, `ProviderStatusResult`, and `AcceptanceResult`
- error and retry semantics
- idempotency expectations for paid-order handoff
- security rules preventing frontend provider, provider cost, price,
  availability, eligibility, and lead time spoofing
- explicit rule that provider pricing output is provider-owned base
  cost/capability data, while PlacamIA backend calculates customer price,
  margin, taxes/fees, discounts, and checkout total

Related docs:

- `docs/flows/main-flow.md`
- `docs/flows/checkout-flow.md`
- `docs/flows/provider-fulfillment-flow.md`
- `docs/planning/provider-adapter-contract.md`
- `docs/planning/provider.md`
- `docs/planning/catalog.md`
- `docs/planning/kits.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`

Related issues:

- #100 Define direct-checkout eligibility boundary and public catalog contract
- #108 Implement local/mock provider adapter availability fixtures

### 2. Local/Mock Provider Adapter

Build first against a deterministic local/mock provider adapter so backend
implementation can continue while partner validation is still in progress.

Outputs:

- local adapter behavior for available, unavailable, manual-quote-only, and
  unsupported items
- deterministic provider cost inputs
- deterministic lead time estimates
- paid-order handoff response with a local provider reference
- handoff status, acceptance, rejection, retry, and failure fixtures for tests
- explicit no-network behavior suitable for deterministic backend tests

Related docs:

- `docs/planning/provider-adapter-contract.md`
- `docs/planning/provider.md`
- `docs/tasks/catalog.md`
- `docs/tasks/checkout.md`
- `docs/validation/product-classification.md`
- `docs/validation/pricing-model.md`
- `docs/validation/availability-model.md`

Related issues:

- #108 Implement local/mock provider adapter availability fixtures

### 3. Adapter-Backed Eligibility and Pricing Foundation

Use the local/mock adapter contract to unblock backend implementation of
catalog eligibility and pricing preview.

Outputs:

- provider-neutral direct-checkout eligibility rules
- backend-owned pricing composition using provider cost inputs
- lead time display contract
- catalog response fields for purchasability and availability state
- tests proving frontend-supplied provider, price, availability, and lead time
  are ignored or rejected
- tests proving frontend-supplied provider cost and eligibility are ignored or
  rejected

Related docs:

- `docs/planning/catalog.md`
- `docs/planning/kits.md`
- `docs/planning/pricing.md`
- `docs/tasks/catalog.md`
- `docs/tasks/checkout.md`

Related issues:

- #109 Add product listing and detail eligibility fields
- #110 Add kit direct-checkout eligibility behavior
- #26 Define Path A pricing rule model and service contracts
- #27 Implement Path A pricing preview service with unit tests
- #28 Create POST pricing preview endpoint for Path A direct checkout

## Parallel Track — Provider Validation

Goal: gather real validation partner data without blocking provider-agnostic
backend architecture.

Findings may name the specific partner that provided them. The roadmap,
contracts, and implementation issues must remain provider-neutral.

### 1. Direct-Checkout Catalog Validation

Goal: determine what can safely be sold in the MVP and map that data into the
provider adapter contract.

Outputs:

- initial direct-checkout product list
- manual-quote exclusion list
- initial direct-checkout kit list
- valid material/size/finish/print combinations
- products that are outsourced or not safe for direct checkout

Source docs:

- `docs/validation/product-classification.md`
- `docs/validation/provider-onboarding-checklist.md`
- `docs/research/provider-partner-question-log.md`
- `docs/tasks/catalog.md`

### 2. Pricing and Availability Validation

Goal: gather provider data that can populate adapter fixtures, seed data, and
future real-provider mappings.

Outputs:

- validation partner pricing/cost input owner
- first provider cost/pricing input table by product/family
- provider availability states and update process
- availability update owner and cadence for adapter fixture maintenance
- rules for made-to-order parametrizable products

Source docs:

- `docs/validation/pricing-model.md`
- `docs/validation/availability-model.md`
- `docs/planning/pricing.md`
- `docs/planning/catalog.md`
- `docs/tasks/catalog.md`

### 3. Commercial and Legal Validation

Goal: avoid implementing payment, refund, payout, invoice, or compliance
promises from engineering guesses.

Outputs:

- customer cancellation/refund/warranty terms
- merchant/seller/invoice model
- validation partner invoice and payout findings
- SLA consequences
- safe compliance/recommendation language

Source docs:

- `docs/validation/commercial-model.md`
- `docs/research/legal-business-questions.md`
- `docs/tasks/checkout.md`

## Phase 2 — Path A Backend Implementation

### 1. Catalog Eligibility

Implement backend representation and public behavior for:

- direct-checkout eligibility
- provider adapter availability
- provider adapter lead time signal
- manual-quote-only exclusion
- kit purchasability

Related docs:

- `docs/tasks/catalog.md`
- `docs/planning/catalog.md`
- `docs/planning/kits.md`

Related issues:

- #100 Define direct-checkout eligibility boundary and public catalog contract
- #109 Add product listing and detail eligibility fields
- #110 Add kit direct-checkout eligibility behavior

### 2. Pricing

Implement deterministic backend pricing for eligible products, kits, and
designs using provider cost/capability inputs from the provider adapter
contract.

Security-critical requirements:

- ignore frontend prices
- ignore frontend provider cost inputs
- reject inactive/unavailable/manual-quote-only items
- reject invalid configurations
- prevent quantity abuse

Related docs:

- `docs/tasks/checkout.md`
- `docs/planning/pricing.md`

Related issues:

- #26 Define Path A pricing rule model and service contracts
- #27 Implement Path A pricing preview service with unit tests
- #28 Create POST pricing preview endpoint for Path A direct checkout

### 3. Checkout and Orders

Implement:

- checkout eligibility gate
- cancellation/refund terms acknowledgement
- draft order creation
- order ownership/security checks
- order status endpoint
- `cancellation_requested`

Related docs:

- `docs/tasks/checkout.md`
- `docs/planning/orders.md`
- `docs/flows/checkout-flow.md`

Related issues:

- #101 Implement checkout eligibility gate and terms acknowledgement
- #30 Create Path A Order and OrderItem models, migrations, and tests
- #31 Create POST order endpoint from Path A validated checkout state
- #32 Create GET order status endpoint with Path A tracking tests

### 4. Payments

Implement payment-provider initialization and webhook verification.

Security-critical requirements:

- no card storage
- valid webhook signature required
- replay protection
- no order confirmation from frontend payment claims
- no provider handoff before verified payment

Related docs:

- `docs/planning/payments.md`
- `docs/tasks/checkout.md`

### 5. Provider Handoff and Fulfillment

Implement:

- paid-order payload generation (implemented for local/mock adapter handoff)
- paid-order handoff through the provider adapter after verified payment
  (implemented for the local/mock adapter)
- provider handoff status reconciliation through the provider adapter
- provider acceptance/rejection recording through the provider adapter
- in-production and ready-for-pickup status
- QR shipment event or authorized operator fallback
- delivered status

Related docs:

- `docs/planning/provider.md`
- `docs/flows/provider-fulfillment-flow.md`
- `docs/tasks/checkout.md`

## Phase 3 — MVP Polish

### Admin/Operator Minimums

Only build admin/operator tools required to operate Path A:

- keep the admin/operator endpoint matrix in
  `docs/planning/admin-backoffice.md` aligned with implemented mutations
- provider handoff retry for confirmed paid orders whose adapter transmission
  failed before `sent_to_provider`
- provider handoff status reconciliation for handed-off orders whose local
  state may drift from provider-side state
- cancellation request resolution
- provider acceptance, production progress, shipment, and delivery mutation
  coverage
- availability update and price table maintenance only if seed/manual data
  updates become insufficient

### Documentation and QA

- Update API examples
- Update Bruno examples if applicable
- Verify `/docs` endpoint descriptions
- Keep `docs/api/endpoint-structure.md` updated for every new or changed
  endpoint, especially admin/operator mutations
- Maintain an operator smoke path: paid order -> sent to provider -> accepted
  -> in production -> ready for pickup -> shipped -> delivered
- Run full backend test suite
- Review security-sensitive rejection tests

## Phase 4 — Mobile Placeholder and Future Work

Mobile work should start after backend Path A surfaces are stable enough to
support:

- catalog browsing
- design/customization
- pricing preview
- checkout
- order tracking

The initial screen map for this mobile placeholder is complete. #37 may begin
with static/mock data and navigation placeholders as long as it does not present
documented-but-pending backend dependencies as real integrations.

Backend dependencies that must remain visible as gaps during #37:

- customer sign-in/token acquisition beyond authenticated context lookup
- kit detail endpoint
- template and design endpoints
- kit and design pricing contracts
- customer-visible cancellation/refund terms content source
- provider-specific payment initialization response
- customer payment-status refresh path
- customer order list and full order detail endpoints

Future work:

- RFQ/manual-quote flow
- provider dashboard
- CSV availability upload
- secure provider links
- exact inventory
- standalone template endpoint expansion beyond critical checkout/design needs
- AI-assisted recommendations or variations
