# RFQ Pivot Canonical Documentation Impact

(Discovery Phase / Non-Canonical)

## MVP Status

The RFQ pivot was not selected for the MVP. PlacamIA is proceeding with Path A:
direct checkout for fully parametrizable, backend-priceable products and kits.
This impact map remains a future-reference checklist only if the team later
reopens an RFQ/provider-confirmed checkout pivot.

## Purpose

This document identifies canonical PlacamIA docs that would need to change if
PlacamIA officially pivots from direct catalog checkout to an RFQ-based,
provider-mediated checkout flow.

This is not the migration itself. It is an impact map.

Current canonical source of truth remains under `docs/flows/`,
`docs/planning/`, and `docs/architecture/` until the RFQ pivot is explicitly
approved.

## Pivot Summary

Current canonical MVP flow:

```text
Catalog
    ->
Template/customization
    ->
Backend pricing
    ->
Checkout
    ->
Payment
    ->
Provider handoff
```

Proposed RFQ flow:

```text
RFQ draft
    ->
Submitted RFQ version
    ->
Provider confirmation or counter-proposal
    ->
Customer acceptance
    ->
Checkout
    ->
Payment
    ->
Paid-order provider handoff
```

## High-Impact Canonical Docs

### `docs/flows/main-flow.md`

Current role:

- Canonical MVP system flow.
- Defines catalog/customize/price/checkout/payment/provider handoff sequence.

RFQ impact:

- Replace direct pricing-to-checkout path with RFQ submission and provider
  confirmation gate.
- Add RFQ versioning.
- Add provider confirmation/counter-proposal/rejection paths.
- Add customer acceptance before checkout.
- Add quote expiration path.
- Add final paid-order handoff after verified payment.
- Clarify that provider confirmation is not the production trigger; paid order
  is.

Suggested change type:

- Major rewrite if RFQ pivot is accepted.

### `docs/flows/checkout-flow.md`

Current role:

- Checkout-specific flow.

RFQ impact:

- Checkout must require current, non-expired, customer-accepted provider
  confirmation.
- Checkout must show cancellation/refund terms before payment.
- Checkout must require required final design/content approvals before payment.
- Failed payment should not create a paid order.
- Payment retry should be allowed only while confirmation remains valid.

Suggested change type:

- Major rewrite.

### `docs/planning/pricing.md`

Current role:

- Backend-calculated pricing.
- Pricing preview endpoint.

RFQ impact:

- Pricing becomes provider-dependent.
- V1 may use provider-confirmed pricing instead of pure automated pricing.
- Hybrid pricing may calculate suggested price that provider confirms or
  adjusts.
- Provider price adjustments require reason category and optional note.
- Checkout uses accepted provider confirmation, not frontend values.
- Legal/payment blockers remain relevant.

Suggested change type:

- Major revision.

### `docs/planning/orders.md`

Current role:

- Order creation and status lifecycle.

RFQ impact:

- Order should be created from accepted provider confirmation after verified
  full payment.
- Paid order becomes production trigger.
- Need relationship to RFQ, RFQVersion, ProviderConfirmation, and
  CustomerAcceptance.
- Cancellation policy becomes provider-customizable with quote-level overrides.
- Customer cancellation becomes request/approval flow, not automatic mutation.

Suggested change type:

- Major revision.

### `docs/planning/payments.md`

Current role:

- Payment verification before order fulfillment.

RFQ impact:

- Real payment implementation is blocked until legal/business questions are
  answered.
- Payment initialization must validate provider confirmation is current,
  accepted, non-expired, and approved for checkout.
- Payment failures keep accepted confirmation usable until `valid_until`.
- Payment webhooks remain idempotent.
- Full payment only for v1.

Suggested change type:

- Major revision, but legal blocker must be resolved first.

### `docs/planning/provider.md`

Current role:

- Provider handoff after confirmed order.

RFQ impact:

- Split provider integration into two flows:
  - inventory/availability communication
  - quote/order/fulfillment confirmation communication
- Add provider capability profile concept.
- Add provider-product availability concept.
- Add operator-mediated v1 confirmation.
- Add final paid-order handoff after payment.
- Add provider status updates and idempotency requirements.

Suggested change type:

- Major revision.

### `docs/planning/templates-designs.md`

Current role:

- Template, TemplateField, and Design customization rules.

RFQ impact:

- Clarify how Design relates to RFQ.
- Design stores validated customization intent.
- RFQ stores supporting files/evidence.
- ProductionAsset represents files approved for manufacturing.
- File-driven customization flow must be defined.
- Customer final design/content approval may be required before checkout.

Suggested change type:

- Moderate to major revision.

### `docs/planning/security.md`

Current role:

- Security planning and hardening roadmap.

RFQ impact:

- Add RFQ ownership/authorization rules.
- Add provider confirmation authorization/audit rules.
- Add attachment security requirements.
- Add production asset validation rules.
- Add idempotency expectations for RFQ submission, confirmation, acceptance,
  payment, handoff, and status updates.
- Add tests for stale/expired/non-current confirmation rejection.

Suggested change type:

- Major revision.

## Architecture Docs

### `docs/architecture/domain-model.md`

RFQ impact:

- Add or revise concepts:
  - Provider
  - ProviderCapabilityProfile
  - ProviderProduct
  - ProviderAvailability
  - RFQ
  - RFQVersion
  - ProviderConfirmation
  - ProviderConfirmationAudit
  - CustomerAcceptance
  - RFQAttachment
  - RFQAddendum
  - ProductionAsset
  - ProviderOrderHandoff
  - ProviderOrderStatusEvent
- Decide whether RFQ replaces Quote or lives beside Quote.

Suggested change type:

- Major revision.

### `docs/architecture/database-diagram.dbml`

RFQ impact:

- Add the RFQ/provider integration entities once canonical model is decided.
- Represent relationships and constraints.
- Add indexes/unique constraints for current confirmation and idempotency keys.

Suggested change type:

- Major revision after domain model is approved.

### `docs/architecture/testing.md`

RFQ impact:

- Add test patterns for RFQ lifecycle.
- Add security tests for ownership and provider/operator access.
- Add rejection tests for:
  - expired confirmation
  - stale confirmation
  - non-current confirmation
  - frontend-provided price
  - invalid attachment
  - unauthorized RFQ access
  - duplicate handoff retry
  - replayed payment webhook
- Add state-transition tests.

Suggested change type:

- Major revision.

### `docs/architecture/security.md`

RFQ impact:

- Add RFQ-specific threats:
  - quote tampering
  - provider confirmation spoofing
  - attachment exposure
  - production asset misuse
  - stale quote checkout
  - duplicate provider handoff
  - unauthorized provider/customer access
- Add mitigation rules and audit expectations.

Suggested change type:

- Major revision.

### `docs/architecture/system-overview.md`

RFQ impact:

- Update system narrative from direct checkout to RFQ/provider-mediated
  checkout.
- Describe provider integration as capability-based and multi-provider-ready.

Suggested change type:

- Moderate revision.

## API Docs

### `docs/api/endpoint-structure.md`

RFQ impact:

- Add future RFQ endpoint groups.
- Reconsider pricing/checkout endpoints around provider confirmation.

Possible future groups:

- `/api/v1/rfqs`
- `/api/v1/rfqs/{rfq_id}/versions`
- `/api/v1/rfqs/{rfq_id}/attachments`
- `/api/v1/provider-confirmations`
- `/api/v1/provider-availability`
- `/api/v1/provider-handoffs`

Suggested change type:

- Major revision after flow/model decisions.

### `docs/api/api-style.md`

RFQ impact:

- Possibly add conventions for state transitions, idempotency keys, file
  uploads, and audit-sensitive endpoints.

Suggested change type:

- Moderate revision.

### `docs/api/examples.md`

RFQ impact:

- Add RFQ lifecycle examples.
- Add provider confirmation and checkout unlock examples.
- Add attachment examples after file rules are defined.

Suggested change type:

- Moderate revision.

## Product Docs

### `docs/product/mvp-scope.md`

RFQ impact:

- Decide whether RFQ becomes MVP scope.
- If yes, update "request quote/pricing" and checkout assumptions.
- Clarify direct checkout is not available until provider confirmation.

Suggested change type:

- Major revision.

### `docs/product/user-flows.md`

RFQ impact:

- Add RFQ customer flow.
- Add provider confirmation/customer acceptance flow.
- Add notification/revisit flow.

Suggested change type:

- Major revision.

### `docs/product/business-logic-overview.md`

RFQ impact:

- Add provider-dependent pricing.
- Add availability classes.
- Add RFQ versioning and confirmation immutability.
- Add cancellation/refund terms before checkout.

Suggested change type:

- Major revision.

### `docs/product/provider-handoff.md`

RFQ impact:

- Clarify difference between provider quote confirmation and paid-order handoff.
- Add idempotent handoff expectations.
- Add v1 manual/operator-mediated handoff option.

Suggested change type:

- Major revision.

## Planning Docs With Smaller Impact

### `docs/planning/catalog.md`

RFQ impact:

- Add provider-specific catalog item concept if canonical.
- Clarify that catalog browsing may lead to RFQ, not direct checkout.
- Keep public catalog rules for active products/kits.

Suggested change type:

- Moderate revision.

### `docs/planning/kits.md`

RFQ impact:

- Kits may become RFQ line items or prefilled RFQ bundles.
- Kit pricing may require provider confirmation.
- Kit availability may be provider-dependent.

Suggested change type:

- Moderate revision.

### `docs/planning/admin-backoffice.md`

RFQ impact:

- Add operator-mediated provider confirmation.
- Add audit requirements.
- Add future provider dashboard boundary.

Suggested change type:

- Moderate revision.

### `docs/planning/foundation.md`

RFQ impact:

- Update references if RFQ becomes central MVP architecture.

Suggested change type:

- Minor to moderate revision.

### `docs/planning/docs.md`

RFQ impact:

- Add RFQ docs tasks once pivot is approved.

Suggested change type:

- Minor revision.

## Low or Deferred Impact Docs

### `docs/planning/mobile-placeholder.md`

Likely impact:

- Later mobile UX may need RFQ status and notifications.

Suggested change type:

- Deferred.

### `docs/tasks/catalog.md`

Likely impact:

- Existing catalog tasks may remain valid, but future catalog tasks should note
  RFQ behavior.

Suggested change type:

- Minor or deferred.

### `docs/tasks/checkout.md`

Likely impact:

- Checkout tasks would need RFQ confirmation prerequisites.

Suggested change type:

- Moderate revision if task docs remain active.

### `docs/timeline.md`

Likely impact:

- Timeline changes if RFQ becomes MVP.

Suggested change type:

- Moderate revision after product decision.

## Suggested Migration Order If Pivot Is Approved

1. Create canonical RFQ flow doc under `docs/flows/`.
2. Update `docs/flows/main-flow.md`.
3. Update `docs/product/mvp-scope.md`.
4. Update `docs/architecture/domain-model.md`.
5. Update `docs/planning/provider.md`.
6. Update `docs/planning/pricing.md`.
7. Update `docs/planning/orders.md`.
8. Update `docs/planning/payments.md`, after legal/payment blocker is resolved.
9. Update `docs/planning/templates-designs.md`.
10. Update `docs/planning/security.md`.
11. Update `docs/architecture/testing.md`.
12. Update API docs.
13. Update product/user-flow docs.
14. Create implementation issues from the updated planning docs.

## Guardrails

- Do not implement RFQ behavior from research docs alone.
- Do not silently change canonical flow diagrams.
- Do not implement production payment until legal/business questions are
  answered.
- Do not implement file uploads without file validation/security planning.
- Do not implement provider dashboard/API before provider terms and
  authorization rules are defined.
- Do not require exact provider inventory for v1.

## Related Research

- `docs/research/rfq-provider-integration-proposal.md`
- `docs/research/rfq-flow-draft.md`
- `docs/research/rfq-future-data-model.md`
- `docs/research/relieves-partner-proposal.md`
- `docs/research/relieves-partner-question-checklist.md`
- `docs/research/legal-business-questions.md`
