# RFQ-Based Provider Integration Proposal

(Discovery Phase / Non-Canonical)

## MVP Status

This RFQ proposal is superseded for the MVP by Path A: direct checkout for
fully parametrizable, backend-priceable products and kits. It remains useful as
future research for manual-quote/custom work, but it must not drive MVP
implementation unless the canonical flow and planning docs are explicitly
changed.

## Purpose

This proposal summarizes a possible PlacamIA pivot toward an RFQ-based provider
integration model.

RFQ means request for quote: the customer submits a structured request, the
provider confirms or adjusts the quote, and checkout opens only after
confirmation.

Relieves de Colombia is treated as a possible first provider, not as the only
provider. The proposal is designed for a future where PlacamIA may work with
many providers that have different catalog, pricing, inventory, and operational
maturity levels.

## Executive Summary

PlacamIA should not try to become a provider's inventory system or fix a
provider's internal operations.

Instead, PlacamIA should become a structured RFQ and transaction layer for
configurable signage commerce:

```text
Customer creates RFQ
    ->
Provider confirms price, feasibility, lead time, and scope
    ->
Customer accepts confirmed quote and required design/content proof
    ->
Customer pays in full
    ->
PlacamIA sends paid-order handoff to provider
    ->
Provider fulfills and reports status
```

For Relieves, the recommended first version is manual and operator-mediated:

- customer submits a structured RFQ in PlacamIA
- PlacamIA/operator sends or communicates the RFQ to Relieves
- Relieves confirms outside the platform
- PlacamIA/operator records the provider confirmation
- customer reviews the confirmed quote
- checkout unlocks only after confirmation and any required customer approval
- after payment, PlacamIA sends a final paid-order handoff

## Why RFQ Fits PlacamIA

The provider domain appears to be slow, custom, and confirmation-heavy because:

- clients often arrive after failed inspections
- seller expertise shapes recommendations
- pricing depends on material, size, printing/engraving, quantity, discounts,
  outsourcing, and changing material costs
- exact inventory may not exist or may not be reliable
- quantities may require human judgment
- custom files, photos, floor plans, and inspection reports may affect scope
- provider feasibility and lead time must be confirmed before promising
  fulfillment

This makes pure self-service ecommerce risky. RFQ-based checkout is slower, but
it prevents false inventory confidence, stale prices, and impossible production
promises.

## Core Product Principles

- Backend/provider-confirmed pricing is the source of truth.
- Checkout is locked until provider confirmation exists.
- A confirmed quote is time-limited.
- Accepted or checked-out quote details are immutable.
- Corrections create a new confirmation or new quote flow.
- Cancellation is allowed as a state transition, not as quote mutation.
- Idempotency is required across provider communication flows.
- Provider inventory capabilities are optional and provider-specific.
- RFQ attachments are private, validated, and versioned.
- Legal/business questions must block production payment decisions.

## Two Separate Integration Flows

PlacamIA should treat provider integration as two separate communication flows.

### 1. Inventory and Availability Communication

This flow answers:

- can this provider currently offer this product or configuration?
- is the item ready-made, made-to-order, outsourced, unavailable, or needs
  confirmation?
- are there material, size, production, or lead-time constraints?

First-version recommendation:

- use soft availability states
- do not require exact stock counts
- store availability at provider-product level first
- allow configuration-level overrides later

Suggested availability states:

- ready-made
- made-to-order
- outsourced
- needs-provider-confirmation
- temporarily-unavailable

Exact stock counts should be an optional provider capability, not a v1
requirement.

### 2. Quote, Order, and Fulfillment Confirmation

This flow answers:

- has the provider confirmed this specific customer RFQ?
- what final price, scope, and lead time did the provider confirm?
- has the customer accepted any counter-proposal?
- has the customer paid?
- has the paid order been sent to the provider?
- has the provider accepted, rejected, produced, shipped, or delivered the
  order?

First-version recommendation:

- send each RFQ to one provider only
- use operator-entered provider confirmation
- send final paid-order handoff only after verified payment
- record provider and order status changes with idempotency and audit history

## Versioned Implementation Options

### V1: Manual RFQ Confirmation

V1 should minimize provider-side software requirements.

Capabilities:

- customer RFQ creation
- provider-specific catalog items
- internal/operator provider assignment
- one RFQ sent to one provider
- provider email notifications
- operator-entered provider confirmations
- customer email and in-app notifications
- provider-confirmed quote checkout gate
- full payment only
- final paid-order handoff
- private RFQ attachments
- operator-mediated attachment sharing

Provider confirmation should include:

- final price
- availability or feasibility
- estimated lead time
- production scope
- quote expiration
- cancellation/refund terms
- whether custom work requires production file review or design approval

Operator-entered confirmations should audit:

- operator_user_id
- provider_contact_method
- provider_contact_reference
- confirmed_at
- full confirmation payload
- price adjustment reason category when price changes

### V1.5: Secure Provider Links

V1.5 can reduce operator work without building a full provider dashboard.

Possible capabilities:

- secure provider confirmation links
- secure expiring attachment download links
- provider action links for confirm/reject/counter-propose
- lightweight provider terms acceptance before link use

This should still preserve:

- idempotency
- audit trail
- confirmation versioning
- customer acceptance before checkout

### V2: Provider Dashboard and Availability Uploads

V2 can introduce provider self-service.

Possible capabilities:

- provider dashboard
- CSV inventory or availability upload
- provider-managed availability classes
- provider quote review queue
- provider status updates
- provider cancellation/refund policy configuration
- provider-level quote expiration defaults
- provider API access for mature partners

V2 should require in-app provider terms acceptance before provider self-service
access.

## Quote and Confirmation Model

`Quote` and `ProviderConfirmation` should be separate records.

Quote:

- records what the customer requested
- preserves customer-provided configuration and RFQ version
- includes supporting files/evidence by version

ProviderConfirmation:

- records the provider response
- includes final price, feasibility, lead time, scope, expiration, cancellation
  terms, rejection reasons, and counter-proposals
- can supersede a prior confirmation before customer acceptance
- becomes immutable once accepted for checkout or used for a paid order

Only one ProviderConfirmation should be current/active for a Quote at a time.
The customer can accept only the current active confirmation.

## RFQ Edit and Version Rules

Draft RFQs can be edited before provider submission.

Once submitted to a provider, the submitted RFQ version should freeze. If the
customer changes it while provider review is pending, PlacamIA should create a
new RFQ version and cancel or supersede the prior pending version.

After provider confirmation, customer changes should be treated as a new quote
or order flow, not as direct edits.

## Counter-Proposals

If a request is not feasible, the provider may:

- reject with a reason
- counter-propose an alternative

Alternatives may change:

- material
- size
- production method
- quantity
- lead time
- price

The customer must explicitly accept a counter-proposal before checkout unlocks.

## Pricing and Expiration

PlacamIA should support provider-dependent pricing:

- provider-confirmed pricing
- backend rule pricing
- hybrid suggested pricing plus provider confirmation

For Relieves, start with provider-confirmed pricing. Later, PlacamIA may
calculate a suggested price and allow the provider to confirm or adjust it.

If provider adjusts PlacamIA's suggested price, require a lightweight adjustment
reason category:

- material_cost_change
- quantity_discount
- custom_work
- outsourced_production
- manual_correction

Provider-confirmed quotes should include `valid_until`.

Quote expiration should support:

- provider-level default expiration
- quote-level override

If payment fails after customer acceptance, the accepted confirmation remains
usable until `valid_until`. No paid order is created unless payment succeeds.
After expiration, checkout locks and requires refreshed provider confirmation.

## Lead Time

Lead time should be structured as:

- min_business_days
- max_business_days
- lead_time_note

Exact dates are too brittle for v1, and free text alone is difficult to compare
or automate.

## Attachments and File-Driven Customization

RFQs should support attachments such as:

- inspection reports
- photos
- floor plans
- reference images

Attachment handling should include:

- limited file types
- file size limits
- private storage
- file metadata
- extension validation
- MIME validation where possible
- audit history

Attachments should belong to the frozen submitted RFQ version.

Customers may add attachments after RFQ submission while provider review is
pending. These should be modeled as clarification/addendum records with
timestamp and audit trail.

After provider confirmation, new attachments should trigger a new or refreshed
quote flow.

File-driven customization should involve both Design and RFQ:

- Design holds validated customization intent used for pricing and order
  generation.
- RFQ holds supporting files and evidence used to understand and confirm the
  request.
- files used for manufacturing need explicit production asset status after
  validation or approval.

A file should not become a production asset just because it was uploaded.

Production asset approval:

- provider approves production feasibility
- customer approves final visible design/content when needed
- PlacamIA operator records or mediates approvals in v1

For v1, required customer approval of final design/content should happen before
checkout.

## Notifications

PlacamIA needs notification and revisit behavior for:

- quote status changes
- provider confirmation changes
- counter-proposals
- quote expiration
- payment status
- order status
- provider rejection
- cancellation

V1 customer channels:

- email
- in-app notifications

V2 customer channel:

- WhatsApp

V1 provider channel:

- email

Provider dashboard notifications can come in v2 or later.

## Payment, Cancellation, and Refunds

V1 should require full payment only after:

- provider confirmation
- customer acceptance of any counter-proposal
- customer approval of required final design/content

Partial payments, deposits, balances, and partial capture are out of scope for
v1.

Paid-order cancellation should be provider-customizable, but the default should
be no customer cancellation after payment.

Customers may request cancellation, but actual cancellation depends on:

- provider policy
- order state
- operator/provider approval

Cancellation and refund policy should support:

- provider-level default
- quote-level override

The confirmed quote checkout summary must show the exact cancellation/refund
terms before payment.

## Legal and Business Blockers

Production payment/checkout implementation should be blocked until the
customer-contract model is answered by someone with legal/accounting/business
background.

Open question:

- Is the customer contract with PlacamIA, with the provider, or with PlacamIA
  acting as a marketplace/intermediary?

This affects:

- merchant of record
- seller of record
- invoices
- taxes
- refunds
- chargebacks
- cancellation terms
- provider liability
- customer support
- dispute handling
- terms of service

Related doc:

- `docs/research/legal-business-questions.md`
- `docs/research/relieves-partner-proposal.md`
- `docs/research/rfq-flow-draft.md`
- `docs/research/rfq-future-data-model.md`
- `docs/research/rfq-canonical-doc-impact.md`

Prototype flows may continue with fake or manual payment states, but real
payment/checkout, invoices, refunds, taxes, and liability-sensitive checkout
copy should wait for the legal/business answer.

## Canonical Documentation Status

This proposal is not yet canonical.

The existing MVP docs still describe a more direct catalog/customize/price/
checkout flow. The RFQ direction should remain in research until PlacamIA
explicitly decides to pivot the canonical MVP flow.

Before implementation depends on RFQ behavior, update and reconcile:

- `docs/flows/main-flow.md`
- `docs/flows/checkout-flow.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/planning/provider.md`
- `docs/planning/templates-designs.md`
- `docs/planning/security.md`
- `docs/architecture/domain-model.md`
- `docs/architecture/testing.md`

## Implementation TODOs

- Define canonical RFQ state lifecycle.
- Define Quote and ProviderConfirmation entities.
- Define RFQ versioning and supersession behavior.
- Define provider capability profile fields.
- Define provider-product availability model.
- Define inventory and availability communication options.
- Define quote confirmation communication options.
- Define paid-order handoff communication options.
- Define provider order-status update options.
- Define customer notification and revisit behavior.
- Define provider email notification templates.
- Define operator-entered confirmation audit events.
- Define RFQ attachment validation and storage rules.
- Define file-driven customization flow.
- Define production asset approval flow.
- Define cancellation/refund policy model.
- Define legal/business answer for merchant/seller/customer-contract model.
- Reconcile canonical planning docs before implementation.

## Recommended Next Step

Use this proposal to decide whether PlacamIA should officially pivot from a
direct checkout MVP to an RFQ-based provider-mediated checkout MVP.

If yes, the next artifact should be a canonical RFQ flow document under
`docs/flows/`, followed by planning doc updates and implementation issues.
