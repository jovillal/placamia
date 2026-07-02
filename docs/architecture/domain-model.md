# Domain Model

## Purpose

This document summarizes PlacamIA domain entities and their current MVP status.
It must stay aligned with the SQLAlchemy models, migrations, and canonical
planning docs.

The MVP follows Path A: direct checkout for fully parametrizable,
backend-priceable products and kits, with provider-neutral fulfillment after
verified payment.

## Critical Rules

- Product = sellable catalog item.
- Kit = curated bundle of Products.
- Template = reusable design base.
- Design = backend-validated customized instance of a Template.
- Templates and Designs are separate entities.
- Provider assignment, pricing, checkout, payment, order, and handoff decisions
  are backend-owned.
- AI generation, credit systems, RFQ/manual quote flow, exact inventory, and
  customer provider choice are out of MVP scope unless canonical docs change.

## Implemented MVP Foundation

These entities currently exist in SQLAlchemy models and migrations.

### User

Represents an account that can authenticate against protected backend behavior.

Current data fields:
- id
- email
- full_name
- role
- is_active
- created_at
- updated_at

Current relationship rules:
- User role is backend-owned.
- Admin authorization must use the persisted role, never frontend claims.

### AuditLog

Represents a security-relevant administrative event.

Current data fields:
- id
- actor_user_id
- action
- resource_type
- resource_id
- event_details
- created_at

Current relationship rules:
- AuditLog belongs to the acting User.
- Sensitive event detail values must be redacted before persistence.

### Category

Represents a customer-facing grouping for catalog browsing.

Current data fields:
- id
- name
- description
- created_at
- updated_at

Current relationship rules:
- Category may have many Products.

### Product

Represents a sellable catalog item.

Current data fields:
- id
- name
- description
- category_id
- base_price
- is_active
- created_at
- updated_at

Current relationship rules:
- Product belongs to one Category.
- Product may appear inside many KitItems.
- Inactive Products are not returned by public product endpoints.
- `base_price` is foundation catalog data, not a final checkout price.
- Product does not yet store provider assignment, provider availability,
  direct-checkout eligibility, or deterministic pricing rules.

### Kit

Represents a curated bundle of catalog Products.

Current data fields:
- id
- name
- description
- is_active
- created_at
- updated_at

Current relationship rules:
- Kit may have many KitItems.
- Kit is read-only in customer-facing MVP catalog behavior.
- Kit does not store pricing, discount, checkout, provider assignment, or
  provider handoff behavior.

### KitItem

Represents one Product entry inside a Kit.

Current data fields:
- id
- kit_id
- product_id
- quantity
- created_at
- updated_at

Current relationship rules:
- KitItem belongs to one Kit.
- KitItem links to one existing Product.
- KitItem stores quantity metadata only.
- KitItem does not duplicate Product metadata, provider data, or pricing.

### Template

Represents a reusable, catalog-level design base.

Current data fields:
- id
- name
- description
- is_active
- created_at
- updated_at

Current relationship rules:
- Template may have many TemplateFields.
- Template may have many Designs.
- Inactive Templates cannot be used to create valid Designs.

### TemplateField

Represents a configurable input definition attached to a Template.

Current data fields:
- id
- template_id
- field_name
- field_type
- is_required
- allowed_values
- display_order
- is_active
- created_at
- updated_at

Current relationship rules:
- TemplateField belongs to one Template.
- TemplateField defines allowed customization inputs.
- TemplateField does not store user customization values.
- MVP `field_type` values are `text`, `select`, `number`, and `boolean`.
- `allowed_values` is used only by field types that explicitly support it.

### Design

Represents a user-customized instance derived from a Template.

Current data fields:
- id
- template_id
- customization_values
- created_at
- updated_at

Current relationship rules:
- Design belongs to one valid Template.
- Design stores validated customization values.
- Design does not store TemplateField definitions.
- Design customization values are keyed by TemplateField `field_name`.
- Rejected customization must not create a Design record.

### Order

Represents a customer purchase created from backend-validated checkout state.

Current data fields:
- id
- customer_id
- status
- cancellation_requested_from
- subtotal_amount
- discount_amount
- tax_amount
- total_amount
- currency
- payment_provider_reference
- payment_verified_at
- assigned_provider_id
- provider_handoff_reference
- provider_handoff_sent_at
- terms_policy_version
- created_at
- updated_at

Current relationship rules:
- Order belongs to the authenticated customer.
- Order has many OrderItems.
- Order may have many persisted Payments over time.
- Order totals come from backend pricing only.
- Order state follows the canonical lifecycle in `docs/flows/main-flow.md`.
- Provider handoff success records `sent_to_provider`, provider handoff
  reference, and handoff sent timestamp.
- Customer cancellation after payment is a request, not an automatic
  cancellation.

### Payment

Represents a persisted payment attempt or provider-confirmed payment record
linked to an Order.

Current data fields:
- id
- order_id
- status
- amount
- currency
- payment_provider_reference
- verified_at
- created_at
- updated_at

Current relationship rules:
- Payment belongs to one Order.
- Order may have many Payments over time.
- Payment stores only payment-safe persisted fields.
- Card data, raw provider payloads, and secrets must not be stored.
- Payment persistence does not itself confirm orders, initialize payments, or
  trigger provider handoff.

### PaymentWebhookEvent

Represents a durable replay key for one trusted provider-neutral payment
webhook event.

Current data fields:
- id
- event_id
- source
- order_id
- payment_id
- received_at

Current relationship rules:
- PaymentWebhookEvent may link to one Order when the webhook references a known
  backend order.
- PaymentWebhookEvent may link to one Payment after the webhook payment record
  is created or updated.
- PaymentWebhookEvent stores only replay-safe identifiers and timestamps.
- Raw webhook payloads, signatures, secrets, card data, and full payment
  details must not be stored.
- Replayed event ids must not reapply Payment, Order, checkout, or provider
  handoff state.

### OrderItem

Represents an immutable purchased item snapshot inside an Order.

Current data fields:
- id
- order_id
- item_type
- product_id
- kit_id
- template_id
- design_id
- display_name
- customer_safe_description
- selected_options
- quantity
- unit_price_amount
- line_subtotal_amount
- line_discount_amount
- line_tax_amount
- line_total_amount
- currency
- assigned_provider_id
- provider_pricing_reference
- provider_payload_snapshot
- created_at

Current relationship rules:
- OrderItem belongs to one Order.
- OrderItem may reference Product, Kit, Template, and Design records for
  traceability.
- OrderItem captures enough product, kit, design, pricing, and provider
  assignment data to support payment, tracking, and provider handoff.
- OrderItem must not depend on raw frontend payloads for fulfillment data.
- Provider handoff uses immutable snapshot fields instead of recomputing from
  mutable catalog state.

## Planned Path A Entities

These entities are required by the current planning docs but are not yet
implemented. Each must be introduced through scoped issues, tests, and Alembic
migrations.

### Provider

Represents a configured manufacturing partner that can fulfill eligible
direct-checkout items.

Expected relationship rules:
- Provider data is backend-owned.
- Public checkout must not allow the frontend to choose, spoof, or override the
  assigned provider.
- Provider-specific findings may be captured in research docs, but the domain
  model remains provider-neutral.

### ProviderAvailability

Represents a provider-specific operational availability signal for the current
catalog period.

Expected relationship rules:
- Availability is a soft operational signal, not exact inventory reservation.
- Availability must be backend-owned.
- Availability participates in direct-checkout eligibility.

### DirectCheckoutEligibility

Represents backend-derived eligibility for a Product, Kit, or Design
configuration to proceed through pricing and checkout.

Expected relationship rules:
- Eligibility depends on active catalog state, provider assignment,
  provider availability, valid configuration, quantity rules, and deterministic
  backend pricing.
- Manual-quote-only, unavailable, inactive, or non-priceable items must not
  enter direct checkout.

### PricingRule

Represents deterministic backend pricing logic for direct-checkout items.

Expected relationship rules:
- Backend pricing is the source of truth.
- Frontend prices, subtotals, discounts, taxes, and totals are ignored or
  rejected.
- Pricing preview must not create Order, Payment, or provider handoff records.

### ProviderHandoff

Represents durable provider handoff event/history beyond the current Order
handoff trace fields.

Expected relationship rules:
- The current implementation records successful local/mock provider handoff
  transmission on Order.
- A dedicated ProviderHandoff entity may be introduced later if operational
  retry, history, audit, or reconciliation needs outgrow the current minimal
  Order trace fields.
- Handoff history must be generated from persisted backend data and remain
  idempotent where possible.

### Shipment

Represents shipment state after provider preparation.

Expected relationship rules:
- `ready_for_pickup -> shipped` requires a valid carrier QR pickup event or an
  authorized operator fallback.
- Customer-facing status must not expose internal provider details.

## Deferred Or Out Of Scope

These concepts are not part of the current direct-checkout MVP implementation.

- RFQ/manual quote flow
- Provider-confirmed checkout before payment
- Customer provider choice
- Exact inventory reservation
- Provider dashboard
- Automated provider payout, invoicing, or SLA enforcement
- Project workspace behavior
- AI-assisted design variation generation
- Credit or gamified credit systems
