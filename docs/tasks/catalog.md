# Catalog Tasks

## Purpose

Track executable catalog work for the Path A MVP.

Path A means direct checkout is available only for products and kits that are
active, compatible with provider adapter boundary responses, and
backend-priceable.

## Source Documents

- `docs/flows/catalog-flow.md`
- `docs/planning/catalog.md`
- `docs/planning/kits.md`
- `docs/planning/pricing.md`
- `docs/planning/provider-adapter-contract.md`
- `docs/validation/product-classification.md`
- `docs/validation/availability-model.md`
- `docs/validation/provider-onboarding-checklist.md`
- `docs/research/path-a-provider-research-summary.md`
- `docs/research/provider-partner-question-log.md`

## Current Baseline

Implemented:

- category model and endpoint
- product model and list/detail endpoints
- product listing category filter and pagination for the public browse contract
- kit and kit item models
- public kit listing endpoint
- active product filtering for public catalog behavior

Still needed for Path A:

- direct-checkout eligibility boundary and public catalog contract (#100)
- local/mock provider adapter availability fixtures (#108)
- product listing/detail eligibility fields (#109)
- kit direct-checkout eligibility behavior (#110)
- approved public kit visibility and content response contract (#172)
- seed/admin data updates after validation partner findings are available (#111)
- tests for unavailable/manual-quote-only purchasability behavior in
  implementation issues

## Provider Validation Tasks

These run in parallel with backend implementation. Catalog implementation can
start against the local/mock provider adapter; validation partner answers should
update adapter fixtures, seed data, and future real-provider mappings later.

Answers may name the specific validation partner that provided them, but the
questions and resulting implementation data should stay provider-neutral so
future providers can be onboarded with the same checklist.

- Confirm the initial direct-checkout product list.
- Confirm products that are manual-quote-only and must stay out of checkout.
- Confirm initial kits and whether kit quantities are fixed or editable.
- Confirm valid material, size, finish, print, and engraving combinations.
- Confirm weekly availability process, owner, and expected response format.
- Confirm whether "made to order but parametrizable" is purchasable.
- Confirm products that are outsourced or not safe for MVP direct checkout.

## Implementation Slices

### 1. Direct-Checkout Eligibility Boundary (#100)

Define the data and response contract that distinguishes:

- visible catalog item
- directly purchasable item
- unavailable item
- manual-quote-only item

Acceptance criteria:

- planning docs and API examples define public fields
- inactive and unavailable items cannot appear as purchasable
- manual-quote-only items do not enter checkout
- visibility and purchasability are documented as separate concepts
- future implementation issues are identified for adapter fixtures, product
  fields, kit behavior, and validation-driven seed data
- no runtime tests required because this slice is documentation-only

### 2. Local/Mock Provider Adapter Availability Fixtures (#108)

Add the minimum backend representation for provider availability through the
provider adapter boundary using the local/mock provider adapter first.
Validation partner data can later replace or extend the adapter fixtures and
seed data.

Acceptance criteria:

- availability state is backend-owned
- implementation does not require a real provider integration
- states support at least:
  - `available`
  - `made_to_order_parametrizable`
  - `temporarily_unavailable`
  - `manual_quote_required`
  - `outsourced_not_mvp_direct`
- unavailable/manual-quote states block checkout eligibility
- tests prove frontend-supplied availability is ignored

### 3. Product Listing and Detail Eligibility (#109)

Expose direct-checkout eligibility consistently in public catalog responses.

Acceptance criteria:

- product listing and detail responses match documented contract
- inactive products remain absent
- unavailable/manual-quote-only products are not shown as purchasable
- query/filter behavior remains validated

### 4. Kit Direct-Checkout Eligibility (#110)

Define and implement purchasability rules for kits.

Acceptance criteria:

- kit is purchasable only when required contents are active, available through
  the provider adapter boundary, and backend-priceable
- kits do not expose inactive products as available contents
- active kits with zero active required contents are hidden
- unavailable, manual-quote-only, or non-priceable required contents are not
  omitted from visible kits; they make the kit visible but not directly
  purchasable with a backend-derived reason
- kit contents return customer-safe product summaries rather than only
  `product_id`
- kit content product summaries use `category_id`
- provider cost, provider assignment, raw provider payloads, and internal
  eligibility inputs are never exposed in public kit contents
- frontend cannot override kit contents, availability, eligibility, lead time,
  or provider cost/capability claims
- implementation is completed by #172 so API examples, schemas, and endpoint
  tests match the approved contract before consumers rely on it

### 5. MVP Seed Data After Validation Findings (#111)

Update seed/catalog data after validation partner findings identify the first
MVP product and kit set.

Acceptance criteria:

- seed data includes only approved direct-checkout items
- manual-quote-only candidates are documented as future/research, not seeded as
  purchasable MVP items
- tests are updated for the final seeded examples

## Security Tests

Catalog issues that touch purchasability must include tests for:

- inactive products are absent from public catalog responses
- unavailable products are not directly purchasable
- manual-quote-only products are not directly purchasable
- frontend-supplied availability is ignored
- kit contents cannot be forged by the frontend

## Out of Scope

- RFQ submission
- exact inventory reservation
- provider dashboard
- customer provider choice unless explicitly scoped later
- compliance-generated product recommendations
- admin UI beyond the minimum needed for backend/operator data
