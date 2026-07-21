# PlacamIA Main Flow

## Purpose

This document defines the MVP system flow for PlacamIA.

It is the source of truth for the automated diagram. The visual diagram should
be generated from this flow, not maintained manually.

## MVP Product Decision

The MVP follows Path A. Product, Kit, and persisted Design configurations can be
pricing-eligible when they are fully parametrizable, compatible with provider
adapter boundary responses, and priceable by backend-owned rules. Persisted
Design pricing eligibility does not by itself implement Design order creation.

The MVP does not use an RFQ gate before checkout. Provider acceptance or
rejection happens through the provider adapter boundary after verified payment
as part of the paid-order handoff.
Products,
configurations, or kits that require manual provider quoting must not be sold
through direct checkout until their behavior is documented and approved.

## Flow Diagram

```mermaid
flowchart TD
    %% User lane
    U1[User browses catalog]
    U2[User selects template]
    U3[User customizes design]
    U4[User requests pricing]
    U5[User reviews cancellation terms]
    U6[User confirms checkout]
    U7[User completes payment]
    U8[User opens order history]
    U9[User tracks order]

    %% Backend lane
    B1[Fetch categories, products, kits]
    B2[Return template and fields]
    B3[Validate customization]
    B4[Create design]
    B5[Load Product, Kit, or owner-scoped persisted Design]
    B6[Revalidate configuration and direct-checkout eligibility]
    B7[Calculate backend pricing]
    G1{Order creation implemented for item type?}
    B8[Create draft order]
    B9[Initialize payment]
    B10[Verify payment webhook]
    B11[Confirm order]
    B12[Prepare paid-order provider payload]
    B13[Provider adapter handoff]
    B14[Update order status]
    B15[List authenticated customer's Order summaries]
    B16[Return owner-scoped persisted totals and lifecycle states]

    %% Database lane
    D1[(Products, Kits, and KitItems)]
    D2[(Templates + TemplateFields + Product anchor)]
    D3[(Customer-owned Designs)]
    D4[(Provider adapter pricing and eligibility responses)]
    D5[(Order + OrderItems)]
    D6[(Payment)]
    D7[(Order status)]

    %% Provider lane
    P1[Assigned provider receives paid order]
    P2{Provider accepts order?}
    P3[Manufacture order]
    P4[Prepare package with QR]
    P5[Carrier scans QR at pickup]
    P6[Deliver order]

    U1 --> B1 --> D1
    B1 --> U2
    U2 --> B2 --> D2
    B2 --> U3
    U3 --> B3 --> D2
    B3 --> B4 --> D3
    B4 --> U4
    U4 --> B5
    B5 -->|Product or Kit| D1
    B5 -->|Design Template and Product| D2
    B5 -->|Owned Design| D3
    D1 --> B6
    D2 --> B6
    D3 --> B6
    B6 --> D4 --> B7
    B7 --> G1
    G1 -->|Product| U5
    G1 -->|Kit or persisted Design| R7[Return pricing preview; order creation remains future work]
    U5 --> U6
    U6 --> B8 --> D5
    B8 --> B9
    B9 --> U7
    U7 --> B10 --> D6
    B10 --> B11
    B11 --> D5
    B11 --> B12 --> D5
    B12 --> B13 --> P1
    P1 --> P2
    P2 -->|yes| B14
    P2 -->|yes| P3 --> P4 --> P5 --> B14
    P5 --> P6 --> B14
    B14 --> D7

    %% Rejection paths
    B3 -. invalid customization .-> R1[Reject request]
    B6 -. not eligible for direct checkout .-> R2[Hide from checkout or reject request]
    B7 -. invalid pricing input .-> R3[Reject pricing request]
    B10 -. invalid or failed payment .-> R4[Do not confirm order]
    B13 -. transmission failed .-> R5[Keep confirmed and retry without duplicate handoff]
    P2 -->|no| R6[Mark provider rejection]

    U8 --> B15 --> D5
    D5 --> B16 --> U8
    U8 --> U9
    D7 --> U9
```

## Design Lifecycle

The MVP Design lifecycle is:

1. Template selected
2. Customization submitted
3. Customization validated by the backend
4. Design persisted only after successful validation
5. Design available for backend pricing

Rejected customization must not create a Design record. Templates and Designs
remain separate domain concepts: a Template is reusable catalog data, while a
Design is one validated customized instance derived from a Template.

Persisted Design pricing reloads the owner-scoped Design, follows its required
Template-to-Product relationship, revalidates current TemplateField rules, and
uses only backend-owned data for provider checks and arithmetic. This pricing
preview does not create an Order, Payment, or provider handoff.

## Customer Order History

Authenticated customers can list only their own persisted Order summaries
before opening tracking. The list is owner-scoped in database list and count
queries, ordered by `created_at DESC, id DESC`, and exposes persisted lifecycle,
currency, total, and timestamp fields only. It does not recalculate historical
totals or load OrderItems, Payments, customer relationships, provider details,
or cancellation provenance. Opening an entry continues to the existing
owner-scoped tracking flow without changing lifecycle ownership or mutation
rules.

## Direct Checkout Eligibility

Before pricing, the backend must verify that every Product, Kit, and persisted
Design configuration is eligible for the requested preview. Product checkout
repeats backend validation before order creation:

1. Product or Kit is active, or the persisted Design's Template and related
   Product are active
2. Provider adapter availability for the current catalog period is compatible
   with sale
3. Selected material, size, finish, quantity, and template fields are valid
4. Backend pricing rules can calculate the final amount deterministically
5. No manual quote, provider confirmation, unsupported file review, or custom
   production decision is required

If any item fails these checks, pricing is rejected and checkout must not be
initialized. Successful Kit and persisted Design previews remain pricing-only
until their order creation paths are implemented separately.

## Order Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> confirmed: verified payment
    confirmed --> sent_to_provider: adapter handoff sent
    sent_to_provider --> accepted: adapter records provider acceptance
    sent_to_provider --> cancelled: adapter records provider rejection
    accepted --> in_production
    in_production --> ready_for_pickup
    ready_for_pickup --> shipped: carrier QR scan
    shipped --> delivered
    draft --> cancelled: user/payment failure/admin cancel
    confirmed --> cancellation_requested: user requests cancellation
    accepted --> cancellation_requested: user requests cancellation
    in_production --> cancellation_requested: user requests cancellation
    cancellation_requested --> cancelled: approved cancellation or refund
    cancellation_requested --> confirmed: rejected before provider acceptance
    cancellation_requested --> accepted: rejected after provider acceptance
    cancellation_requested --> in_production: rejected during production
```

## Fulfillment Notes

PlacamIA owns the customer relationship, customer payment, customer
notifications, and order tracking. The assigned manufacturing provider produces
and prepares the order, but does not contact the customer directly in the MVP.
Partner-specific validation findings may name the provider that supplied them,
but this flow must remain provider-neutral.

The carrier QR scan is the canonical trigger for moving an accepted order from
`ready_for_pickup` to `shipped`, once the QR mechanism is technically validated
with the selected carrier. Until that validation is complete, an operator may
record the equivalent shipment event without changing the status lifecycle.

Customer cancellation after payment is a request, not an automatic mutation.
The approval rule depends on the order state and the cancellation/refund policy
agreed with the assigned provider and documented by PlacamIA. The customer must
see the applicable terms before payment.

## Planning Documents
- `docs/planning/foundation.md`
- `docs/planning/catalog.md`
- `docs/planning/kits.md`
- `docs/planning/templates-designs.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/planning/provider-adapter-contract.md`
- `docs/planning/provider.md`
- `docs/planning/security.md`
- `docs/planning/admin-backoffice.md`
- `docs/planning/docs.md`
- `docs/planning/mobile-placeholder.md`

## Related Flow Documents

- `docs/flows/catalog-flow.md`
- `docs/flows/checkout-flow.md`
- `docs/flows/provider-fulfillment-flow.md`

## Rule

Manual diagrams are optional presentation artifacts only.

The Mermaid diagrams in this file are the canonical flow representation.
