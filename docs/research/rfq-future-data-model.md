# RFQ Future Data Model Draft

(Discovery Phase / Non-Canonical)

## MVP Status

This model is not part of the MVP. The MVP follows Path A: direct checkout for
fully parametrizable, backend-priceable products and kits. RFQ entities should
not be implemented unless the canonical flow and planning docs are explicitly
changed for a future manual-quote/custom-work phase.

## Purpose

This document drafts a possible future data model for an RFQ-based PlacamIA
flow.

It is not an implementation spec and should not be treated as canonical until
the RFQ pivot is accepted and the planning docs are reconciled.

RFQ means request for quote. In this model, the customer creates a structured
request, the provider confirms or adjusts it, and checkout opens only after the
customer accepts the current provider confirmation.

## Modeling Principles

- Keep customer request data separate from provider response data.
- Preserve submitted RFQ versions instead of editing them in place.
- Keep provider confirmations append-only/versioned for traceability.
- Treat accepted/checked-out confirmation details as immutable.
- Store provider capability and availability separately from transaction state.
- Treat exact stock counts as optional provider capability.
- Keep files private and distinct from production-approved assets.
- Design for manual/operator-mediated v1 and more automated provider workflows
  later.

## Concept Map

```text
Provider
    ->
ProviderProduct
    ->
ProviderAvailability

Customer
    ->
RFQ
    ->
RFQVersion
    ->
RFQAttachment
    ->
ProviderConfirmation
    ->
CustomerAcceptance
    ->
Order
    ->
ProviderOrderHandoff
    ->
ProviderOrderStatusEvent

RFQAttachment
    ->
ProductionAsset
```

## Proposed Entities

### Provider

Represents a company that can fulfill signage work.

Possible fields:

- id
- name
- legal_name
- contact_email
- contact_phone
- is_active
- default_quote_validity_hours
- default_cancellation_policy
- default_refund_policy
- created_at
- updated_at

Notes:

- Provider terms acceptance may be external/contractual for v1.
- In-app provider terms acceptance is needed before provider dashboard, secure
  links, or API access.

### ProviderCapabilityProfile

Represents what a provider can support operationally and technically.

Possible fields:

- id
- provider_id
- supports_manual_quote_confirmation
- supports_rule_based_pricing
- supports_provider_price_confirmation
- supports_exact_inventory
- supports_availability_classes
- supports_lead_time_estimates
- supports_order_status_updates
- supports_custom_design_files
- supports_secure_confirmation_links
- supports_csv_availability_upload
- supports_provider_dashboard
- supports_api_integration
- created_at
- updated_at

Notes:

- Capabilities should drive platform behavior.
- Exact inventory is optional, not required for first integrations.

### ProviderProduct

Represents a provider-specific sellable offering.

Possible fields:

- id
- provider_id
- canonical_product_id nullable
- canonical_template_id nullable
- name
- description
- provider_reference nullable
- is_active
- requires_provider_confirmation
- allows_customization
- allows_attachments
- created_at
- updated_at

Notes:

- Start provider-specific.
- Canonical catalog/template mapping can come later when obvious.
- Do not force multiple providers into the same product model too early.

### ProviderAvailability

Represents provider-product availability.

Possible fields:

- id
- provider_product_id
- availability_state
- min_business_days nullable
- max_business_days nullable
- availability_note nullable
- effective_from nullable
- effective_until nullable
- updated_by_user_id nullable
- created_at
- updated_at

Suggested `availability_state` values:

- ready_made
- made_to_order
- outsourced
- needs_provider_confirmation
- temporarily_unavailable

Notes:

- Availability should live at provider-product level first.
- Configuration-level overrides can be added later.
- Exact stock counts should be optional.

### ProviderAvailabilityOverride

Represents optional configuration-level availability constraints.

Possible fields:

- id
- provider_product_id
- configuration_key
- configuration_value
- availability_state
- min_business_days nullable
- max_business_days nullable
- note nullable
- effective_from nullable
- effective_until nullable
- created_at
- updated_at

Notes:

- Future-facing entity.
- Useful for cases like material, size, printing, engraving, or outsourcing
  constraints.
- Probably not required for v1.

### RFQ

Represents the customer's request process.

Possible fields:

- id
- customer_user_id
- provider_id nullable
- status
- current_version_id nullable
- current_provider_confirmation_id nullable
- created_at
- updated_at
- cancelled_at nullable
- cancellation_reason nullable

Possible status values:

- draft
- submitted
- provider_review
- provider_confirmed
- counter_proposed
- customer_accepted
- checkout_unlocked
- payment_pending
- paid
- sent_to_provider
- in_production
- shipped
- delivered
- expired
- cancelled
- superseded

Notes:

- The exact official status set is still an open question.
- Customer-visible labels may differ from internal statuses.

### RFQVersion

Represents one frozen submitted version of an RFQ.

Possible fields:

- id
- rfq_id
- version_number
- provider_product_id nullable
- submitted_configuration
- submitted_notes nullable
- submitted_at nullable
- submitted_by_user_id
- status
- superseded_by_version_id nullable
- superseded_at nullable
- created_at
- updated_at

Notes:

- Draft data may be edited before submission.
- Submitted RFQ versions should not be edited in place.
- Customer changes after submission create a new version.

### RFQLineItem

Represents one requested item inside an RFQ version.

Possible fields:

- id
- rfq_version_id
- provider_product_id nullable
- product_id nullable
- template_id nullable
- design_id nullable
- quantity
- configuration_values
- customer_notes nullable
- created_at
- updated_at

Notes:

- This may be needed if an RFQ can include multiple signs/products.
- For a very small v1, RFQVersion could store one configuration directly and
  RFQLineItem could be deferred.

### RFQAttachment

Represents a file attached to an RFQ version or clarification/addendum.

Possible fields:

- id
- rfq_id
- rfq_version_id nullable
- addendum_id nullable
- uploaded_by_user_id
- original_filename
- storage_key
- content_type
- file_extension
- file_size_bytes
- checksum nullable
- attachment_purpose
- validation_status
- created_at
- deleted_at nullable

Suggested `attachment_purpose` values:

- inspection_report
- site_photo
- floor_plan
- reference_image
- logo
- editable_artwork
- print_ready_artwork
- other

Suggested `validation_status` values:

- pending_validation
- accepted
- rejected
- quarantined

Notes:

- Attachments must be private.
- Uploaded attachment does not equal production asset.
- Attachment file type and size limits must be defined before implementation.

### RFQAddendum

Represents customer-provided clarification after RFQ submission and before
provider confirmation.

Possible fields:

- id
- rfq_id
- rfq_version_id
- created_by_user_id
- message nullable
- created_at

Notes:

- Use for extra files or clarification while provider review is pending.
- After provider confirmation, new files or changes should trigger a refreshed
  quote flow.

### ProviderConfirmation

Represents the provider's response to an RFQ version.

Possible fields:

- id
- rfq_id
- rfq_version_id
- provider_id
- status
- confirmation_version
- supersedes_confirmation_id nullable
- is_current
- final_price_amount nullable
- currency
- price_adjustment_reason nullable
- price_adjustment_note nullable
- min_business_days nullable
- max_business_days nullable
- lead_time_note nullable
- production_scope
- valid_until nullable
- cancellation_policy
- refund_policy
- requires_customer_design_approval
- requires_production_file_review
- rejection_reason nullable
- counter_proposal_details nullable
- confirmed_at nullable
- created_at
- updated_at

Possible status values:

- draft
- confirmed
- rejected
- counter_proposed
- superseded
- expired
- accepted_by_customer
- cancelled

Notes:

- Separate from RFQ for traceability.
- Provider revisions create a new confirmation version.
- Only one confirmation should be current/active.
- Accepted or checked-out confirmation details should not mutate.

### ProviderConfirmationAudit

Represents audit data for manually entered or provider-supplied confirmations.

Possible fields:

- id
- provider_confirmation_id
- actor_user_id nullable
- actor_type
- provider_contact_method nullable
- provider_contact_reference nullable
- event_type
- event_payload
- created_at

Suggested `actor_type` values:

- placamia_operator
- provider_user
- system

Suggested `event_type` values:

- created
- superseded
- price_adjusted
- rejected
- counter_proposed
- expired
- accepted_by_customer
- cancelled

Notes:

- Required for operator-entered v1 confirmations.
- Should preserve source and reason for manual decisions.

### CustomerAcceptance

Represents the customer's explicit acceptance of the current provider
confirmation.

Possible fields:

- id
- rfq_id
- provider_confirmation_id
- accepted_by_user_id
- accepted_at
- accepted_price_amount
- accepted_currency
- accepted_valid_until
- accepted_cancellation_policy
- accepted_refund_policy
- accepted_production_scope
- accepted_counter_proposal
- created_at

Notes:

- Snapshot acceptance details so checkout cannot be affected by later changes.
- Must reference the current active, non-expired provider confirmation.
- Acceptance should be idempotent.

### ProductionAsset

Represents a file approved for production.

Possible fields:

- id
- rfq_id
- rfq_version_id
- source_attachment_id nullable
- storage_key
- content_type
- file_size_bytes
- production_asset_status
- provider_approved_at nullable
- provider_approved_by nullable
- customer_approved_at nullable
- customer_approved_by_user_id nullable
- operator_user_id nullable
- approval_notes nullable
- created_at
- updated_at

Suggested `production_asset_status` values:

- pending_provider_review
- provider_approved
- customer_approval_required
- customer_approved
- rejected
- superseded

Notes:

- A file becomes production input only after validation/approval.
- Customer approval is required when visible design/content changes.
- For v1, operator may mediate approvals.

### Payment

Represents payment attempt and verified payment state.

Possible RFQ-related fields:

- id
- rfq_id nullable
- order_id nullable
- provider_confirmation_id
- amount
- currency
- status
- provider_reference nullable
- verified_at nullable
- created_at
- updated_at

Notes:

- Production payment implementation is blocked until legal/business questions
  are answered.
- Prototype flows may use fake/manual payment states.
- Payment webhooks must be idempotent.

### Order

Represents a paid order derived from accepted provider confirmation.

Possible RFQ-related fields:

- id
- rfq_id
- provider_id
- provider_confirmation_id
- customer_acceptance_id
- payment_id
- status
- total_amount
- currency
- created_at
- updated_at

Notes:

- Paid order should snapshot what was accepted and paid.
- The provider-confirmed quote is permission to sell.
- The paid order is the production trigger.

### ProviderOrderHandoff

Represents the handoff of a paid order to the provider.

Possible fields:

- id
- order_id
- provider_id
- idempotency_key
- handoff_status
- payload
- sent_at nullable
- acknowledged_at nullable
- failure_reason nullable
- retry_count
- created_at
- updated_at

Suggested `handoff_status` values:

- pending
- sent
- acknowledged
- failed
- cancelled

Notes:

- Must be idempotent.
- Retries must not duplicate provider orders.
- V1 handoff may be email/operator-mediated.

### ProviderOrderStatusEvent

Represents provider fulfillment status updates after paid order handoff.

Possible fields:

- id
- order_id
- provider_id
- idempotency_key nullable
- status
- status_note nullable
- occurred_at
- recorded_by_user_id nullable
- created_at

Possible status values:

- provider_received
- provider_accepted
- provider_rejected
- in_production
- ready_for_pickup
- shipped
- delivered
- cancelled

Notes:

- Some statuses may be internal-only.
- Customer-visible labels should be defined separately.

### NotificationEvent

Represents an event that should notify customer, provider, or operator.

Possible fields:

- id
- recipient_user_id nullable
- recipient_email nullable
- recipient_type
- channel
- event_type
- related_entity_type
- related_entity_id
- status
- payload
- created_at
- sent_at nullable

Suggested channels:

- email
- in_app
- whatsapp_future

Notes:

- V1 customer channels: email and in-app.
- V1 provider channel: email.
- WhatsApp is v2.

## Relationship Notes

```text
Provider 1--1 ProviderCapabilityProfile
Provider 1--many ProviderProduct
ProviderProduct 1--many ProviderAvailability
ProviderProduct 1--many ProviderAvailabilityOverride

Customer/User 1--many RFQ
RFQ 1--many RFQVersion
RFQVersion 1--many RFQLineItem
RFQVersion 1--many RFQAttachment
RFQVersion 1--many RFQAddendum
RFQVersion 1--many ProviderConfirmation

ProviderConfirmation 1--many ProviderConfirmationAudit
ProviderConfirmation 1--0..1 CustomerAcceptance
RFQAttachment 1--0..many ProductionAsset

CustomerAcceptance 1--0..1 Payment
Payment 1--0..1 Order
Order 1--many ProviderOrderHandoff
Order 1--many ProviderOrderStatusEvent
```

## V1 Minimum Candidate

For a manual Relieves pilot, the minimum likely set is:

- Provider
- ProviderCapabilityProfile
- ProviderProduct
- ProviderAvailability
- RFQ
- RFQVersion
- RFQAttachment
- ProviderConfirmation
- ProviderConfirmationAudit
- CustomerAcceptance
- Order
- ProviderOrderHandoff
- ProviderOrderStatusEvent
- NotificationEvent

Likely deferrable:

- ProviderAvailabilityOverride
- RFQLineItem if v1 supports only one requested item
- ProductionAsset if file-driven production is not in first pilot
- provider dashboard users/roles
- exact inventory records
- CSV upload import tables

## Open Modeling Questions

1. Should RFQ replace the existing Quote concept or live beside it?
2. Should RFQ support multiple line items in v1?
3. Should ProviderConfirmation belong to RFQVersion only, or also directly to
   RFQ for easier querying?
4. Which RFQ statuses are customer-visible?
5. Which provider order statuses are customer-visible?
6. Does CustomerAcceptance need a separate table or can it be represented as a
   ProviderConfirmation state transition plus snapshot fields?
7. Should cancellation requests be their own entity?
8. Should provider policies be versioned separately from confirmations?
9. Should attachments and production assets use a shared file table?
10. Which fields require audit history beyond created_at/updated_at?
11. Which entities need idempotency keys?
12. Which fields are blocked by legal/business answers?

## Canonical Documentation Impact

If this model becomes canonical, update:

- `docs/architecture/domain-model.md`
- `docs/architecture/database-diagram.dbml`
- `docs/flows/main-flow.md`
- `docs/flows/checkout-flow.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/planning/provider.md`
- `docs/planning/templates-designs.md`
- `docs/planning/security.md`
- `docs/architecture/testing.md`

Do not implement this model until the RFQ pivot and legal/payment blockers are
resolved.
