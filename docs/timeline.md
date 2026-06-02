# PlacamIA Timeline

## Product Direction

The MVP follows Path A: direct checkout for fully parametrizable,
backend-priceable products and kits.

RFQ/provider-confirmed checkout remains future work for manual/custom products.

## Phase 0 — Completed Foundation

### Completed

- Repo structure
- AGENTS.md
- Pytest baseline
- FastAPI backend foundation
- Security architecture and testing docs
- Catalog/category/product foundations
- Template/design validation foundation
- Kit model and listing foundation
- Path A flow/planning/research reconciliation

## Phase 1 — Provider Validation

Phase 1 outputs must be captured as provider-neutral data from the current
validation partner so PlacamIA can onboard additional manufacturing providers
later. Findings may name the specific partner that provided them; the work plan
must not.

### 1. Direct-Checkout Catalog Validation

Goal: determine what can safely be sold in the MVP.

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

Goal: get enough provider data to implement backend pricing and catalog
eligibility.

Outputs:

- validation partner pricing table owner
- first pricing table by product/family
- weekly availability states and process
- availability update owner and cadence
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
- validation partner invoice and payout process
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
- weekly provider availability
- manual-quote-only exclusion
- kit purchasability

Related docs:

- `docs/tasks/catalog.md`
- `docs/planning/catalog.md`
- `docs/planning/kits.md`

### 2. Pricing

Implement deterministic backend pricing for eligible products, kits, and
designs.

Security-critical requirements:

- ignore frontend prices
- reject inactive/unavailable/manual-quote-only items
- reject invalid configurations
- prevent quantity abuse

Related docs:

- `docs/tasks/checkout.md`
- `docs/planning/pricing.md`

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

- paid-order payload generation
- handoff to assigned provider
- provider acceptance/rejection
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

- availability update
- price table maintenance if not seeded/manual
- provider handoff retry/status update
- cancellation request resolution
- shipment fallback event

### Documentation and QA

- Update API examples
- Update Bruno examples if applicable
- Verify `/docs` endpoint descriptions
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

Future work:

- RFQ/manual-quote flow
- provider dashboard
- CSV availability upload
- secure provider links
- exact inventory
- AI-assisted recommendations or variations
