# Path A Provider Research Summary

(Discovery Phase / Non-Canonical)

## Purpose

Summarize how the provider research should be interpreted now that PlacamIA has
chosen Path A for the MVP.

Canonical implementation decisions still live in `docs/flows/` and
`docs/planning/`. This document explains what the research means for future
product and partner conversations.

## MVP Decision

Path A means:

```text
Direct-checkout catalog
    ->
Backend pricing
    ->
Verified customer payment
    ->
Paid-order handoff to Relieves
    ->
Relieves acceptance, production, pickup, and delivery
```

The MVP should not use RFQ/provider-confirmed checkout before payment.

## What Research Supports for MVP

The research supports a narrow, commerce-first MVP:

- curated catalog of standard products and kits
- simple rules-based customization
- backend-owned price tables
- weekly operational availability from Relieves
- no exact inventory requirement
- full payment before production
- paid-order handoff to Relieves
- Relieves acceptance or rejection after payment
- customer-facing order tracking
- QR pickup scan when technically validated, with operator fallback

## What Research Excludes from MVP

The following remain outside direct checkout:

- products needing manual quote review
- custom products that require file inspection before price
- inspection-driven advisory flows
- exact compliance recommendations with legal promises
- outsourced work with uncertain lead time or price
- provider dashboards, APIs, or secure self-service links
- exact inventory reservation
- automated provider payout, invoicing, or SLA penalty logic

## Research Interpretation

The provider materials point to two business modes:

- Catalog commerce: customer already knows what they want and can select a
  standard product or kit.
- Advisory/compliance sales: customer needs expert help, often after an
  inspection or when interpreting regulations.

Path A starts with catalog commerce. Advisory/compliance sales can become a
future RFQ/manual-quote path after the direct-checkout MVP proves demand.

## Document Map

- `docs/research/relieves-partner-proposal.md`: Path A conversation proposal
  for Relieves.
- `docs/research/relieves-partner-question-checklist.md`: meeting checklist
  for validating Path A with Relieves.
- `docs/research/provider-partner-question-log.md`: unresolved provider
  questions and implementation guardrails.
- `docs/research/legal-business-questions.md`: legal/accounting blockers for
  checkout, refunds, invoicing, provider payout, and compliance language.
- `docs/research/provider-domain-analysis.md`: source analysis of Relieves'
  workbook/catalog semantics.
- `docs/research/provider-workbook-analysis.md`: semantic inventory of the
  NSR10 workbook.
- `docs/research/rfq-*.md`: future-reference research for manual quote/custom
  work, not MVP implementation guidance.

## Immediate Partner Validation Needed

Before implementing Path A features that depend on Relieves, validate:

1. Initial direct-checkout product list
2. Products excluded as manual quote/future RFQ
3. Parametrizable pricing table
4. Valid material/size/finish combinations
5. Weekly availability process and owner
6. SLA for order acceptance, production, pickup, and delivery
7. QR pickup feasibility or operator fallback
8. Cancellation/refund/warranty policy
9. Invoicing and provider payout process
10. Safe compliance/recommendation language

## Future RFQ Trigger

Reopen RFQ planning only when PlacamIA wants to sell products that cannot meet
Path A eligibility:

- price cannot be calculated deterministically
- provider must review feasibility before payment
- customer files must be inspected before scope is known
- quantities require site-specific expert judgment
- lead time depends on outsourcing or unusual materials

When that happens, update canonical flow and planning docs before
implementation.
