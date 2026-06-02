# Provider Partner Question Log

(Discovery Phase / Non-Canonical)

## Purpose

This document tracks follow-up questions for Relieves de Colombia and future
provider partners that emerged from `docs/research/provider-domain-analysis.md`
and Path A reconciliation.

The goal is to separate unresolved provider questions from architectural
decisions. Answers captured here should later be reconciled into canonical
planning documents before implementation work depends on them.

## MVP Read

PlacamIA confirmed Path A for MVP:

```text
Catalog product or kit
    ->
Backend eligibility and pricing
    ->
Customer payment
    ->
Paid-order handoff to Relieves
    ->
Relieves accepts/rejects and fulfills
```

Path A depends on a narrower catalog than the RFQ research assumed. The MVP
should sell only products, kits, and configurations that are:

- active in the public catalog
- fully parametrizable
- compatible with current Relieves availability
- deterministically priceable by backend rules
- not dependent on manual quote review before payment

Products that require manual provider confirmation, complex files, custom
scope, outsourcing uncertainty, or human price adjustment should stay outside
direct checkout and remain candidates for a future RFQ/manual-quote flow.

## Research Interpretation

The provider appears to operate through two overlapping modes:

- compliance-driven advisory sales, especially when clients arrive after a
  failed or upcoming inspection
- catalog-driven commerce, especially when clients already know what they want

Path A should start from the catalog-driven mode. Compliance-driven advisory
work remains valuable, but should not become authoritative automated product
behavior until legal/compliance review and provider validation are complete.

The workbook appears to be an internal parametrization or compliance knowledge
capture initiative rather than a currently operational source of truth. The
Canva/PDF catalog appears closer to the current commercial surface, but not the
final pricing authority.

## Path A Provider Questions

### 1. Direct-Checkout Product Boundary

**Question:** Which products can Relieves reliably fulfill without reviewing a
customer-specific request before payment?

**Why this matters:** These are the only products that should enter direct
checkout.

**Recommended answer:** Start with a small list of standard safety signs and
kits. Exclude products that need manual quote review, custom file review,
uncertain outsourcing, or nonstandard production decisions.

### 2. Manual-Quote Exclusion Boundary

**Question:** Which products or configurations must be excluded from MVP direct
checkout?

**Why this matters:** The exclusion list is as important as the catalog list.
It prevents PlacamIA from selling work that Relieves cannot price or fulfill
reliably after payment.

**Recommended answer:** Tag excluded work as manual-quote/future-RFQ research.
Do not expose those products as purchasable until a canonical flow exists.

### 3. Source of Truth for Recommendations

**Question:** When a client asks what signage they need, who or what is the
current authority for the final recommendation: provider expert, workbook,
Canva catalog, past jobs, inspection feedback, or another source?

**Why this matters:** Path A kits may use curated recommendations, but PlacamIA
must avoid making legal or inspection-guarantee claims.

**Recommended answer:** Treat provider expert judgment and recent inspection
feedback as the current source of truth. Treat the workbook as a draft knowledge
capture artifact until reviewed by legal/compliance experts.

### 4. Scope of Compliance Claims

**Question:** What exact language is acceptable when PlacamIA recommends signs:
can it say "required", "recommended", "commonly requested by inspectors", or
only "suggested based on provided business context"?

**Why this matters:** Product copy, kit descriptions, and checkout disclaimers
must avoid implying guaranteed inspection success.

**Recommended answer:** Use cautious language such as "suggested based on the
information provided" and "commonly requested for this context." Avoid
"guaranteed compliance" and avoid presenting recommendations as legal advice.

### 5. Kit Definition

**Question:** For existing "inspection packages", what determines package
contents: business activity, regulator, physical layout, square meters,
employee count, risk level, prior inspection notes, or manual judgment?

**Why this matters:** Path A kits must be simple enough to price and fulfill.
If quantities depend on a site-specific assessment, the kit should not be sold
as a fixed direct-checkout item.

**Recommended answer:** Model early packages as manually curated kit templates
with simple quantity rules. Treat site-specific advisory kits as future/manual.

### 6. Quantity Estimation Inputs

**Question:** What information does Relieves need to determine quantity safely?

**Why this matters:** Quantity drives pricing, production, and fulfillment. If
the system cannot estimate quantity safely, it should avoid pretending that a
business type alone is enough.

**Recommended answer:** For Path A, let the customer choose quantity within
backend limits or use fixed kit quantities. Do not auto-generate quantities from
business type until compliance logic is validated.

### 7. Pricing Formula Ownership

**Question:** Who owns the current pricing rules for material, size, print type,
engraving, quantity discounts, and manual adjustments?

**Why this matters:** Backend pricing is the source of truth for checkout.
PlacamIA needs a maintainable pricing table, not embedded assumptions.

**Recommended answer:** Assign one Relieves operational owner for base pricing
rules. Keep manual discounts out of MVP direct checkout unless they can be
expressed as deterministic rules.

### 8. Material and Print Compatibility

**Question:** Which material, size, print, engraving, and finish combinations
are valid or invalid?

**Why this matters:** Invalid combinations must be rejected before pricing and
checkout.

**Recommended answer:** Build a small compatibility matrix from provider input
before implementing configurable pricing.

### 9. Availability Semantics

**Question:** If exact inventory is not tracked, how should availability and
delivery time be communicated?

**Why this matters:** Path A uses weekly operational availability, not exact
reservation.

**Recommended answer:** Track soft availability states for MVP:
`available`, `made_to_order_parametrizable`, `temporarily_unavailable`,
`manual_quote_required`, and `outsourced_not_mvp_direct`.

### 10. Provider Handoff Payload

**Question:** What exact information does Relieves need in the paid-order
payload to manufacture without customer contact?

**Why this matters:** PlacamIA owns the customer relationship. Relieves must
receive a complete, unambiguous manufacturing handoff.

**Recommended answer:** Include order id, product ids, quantities, material,
size, finish, template/design specifications, delivery information, and QR or
shipment reference when available.

### 11. Production Statuses

**Question:** Which statuses can Relieves reliably report to PlacamIA?

**Why this matters:** Customer tracking should reflect real operational events.

**Recommended answer:** Start with `accepted`, `in_production`,
`ready_for_pickup`, `shipped`, `delivered`, and `rejected/cancelled`.

### 12. QR Pickup Feasibility

**Question:** Can Relieves and the selected carrier support QR scan at pickup?

**Why this matters:** The canonical flow uses QR scan as the preferred trigger
for `ready_for_pickup -> shipped`.

**Recommended answer:** Validate with the carrier. Until validated, use an
authorized operator fallback for shipment events.

### 13. Outsourcing Rules

**Question:** Which product families, materials, or production methods are
outsourced, and how does outsourcing affect price, lead time, and rejection
risk?

**Why this matters:** Outsourcing uncertainty can make a product unsuitable for
direct checkout.

**Recommended answer:** Capture outsourced work as operational metadata. Exclude
outsourced products from Path A unless price and timing are deterministic.

### 14. Asset Source and Conversion Workflow

**Question:** Which Corel Draw files are authoritative, and what export format
should PlacamIA preserve or generate for provider handoff?

**Why this matters:** Original design files live with Relieves, while PlacamIA
needs template previews and reliable handoff data.

**Recommended answer:** Treat provider-owned Corel files as production source
for now. PlacamIA should store template metadata and previews first.

### 15. Legal Review Cadence

**Question:** Who will review regulation-derived rules, and how often should
they be reviewed or versioned?

**Why this matters:** The matrix may change because it is wrong or because
regulation changes.

**Recommended answer:** Require legal/compliance review before automated
regulation-derived recommendations are treated as authoritative.

## Path A Guardrails

- Do not promote compliance recommendations into checkout behavior until legal
  and provider validation is complete.
- Do not sell products that require manual provider confirmation through direct
  checkout.
- Do not derive authoritative pricing from catalog screenshots or Canva prices.
- Do not promise exact stock unless Relieves has an exact inventory process.
- Do not trigger provider handoff before verified customer payment.
- Do not automate refunds, provider payout, invoicing, or SLA consequences
  until legal/accounting policy is documented.

## Future RFQ Use

The RFQ research remains useful for:

- custom signs
- file-heavy work
- inspection-driven advisory sales
- outsourced work with uncertain price or timing
- products that need provider review before payment

Before any RFQ behavior becomes implementation scope, canonical flow and
planning docs must be updated again.
