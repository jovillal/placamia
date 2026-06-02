# PlacamIA Main Flow

## Purpose

This document defines the MVP system flow for PlacamIA.

It is the source of truth for the automated diagram. The visual diagram should
be generated from this flow, not maintained manually.

## MVP Product Decision

The MVP follows Path A: direct checkout for products and kits that are fully
parametrizable, available for the current catalog period, and priceable by
backend-owned rules.

The MVP does not use an RFQ gate before checkout. Provider acceptance or
rejection happens after verified payment as part of the paid-order handoff.
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
    U8[User tracks order]

    %% Backend lane
    B1[Fetch categories, products, kits]
    B2[Return template and fields]
    B3[Validate customization]
    B4[Create design]
    B5[Validate active direct-checkout eligibility]
    B6[Calculate backend pricing]
    B7[Create draft order]
    B8[Initialize payment]
    B9[Verify payment webhook]
    B10[Confirm order]
    B11[Prepare paid-order provider payload]
    B12[Send paid order to provider]
    B13[Update order status]

    %% Database lane
    D1[(Catalog data)]
    D2[(Templates)]
    D3[(Design)]
    D4[(Pricing rules and availability)]
    D5[(Order + OrderItems)]
    D6[(Payment)]
    D7[(Order status)]

    %% Provider lane
    P1[Relieves receives paid order]
    P2{Relieves accepts order?}
    P3[Manufacture order]
    P4[Prepare package with QR]
    P5[Carrier scans QR at pickup]
    P6[Deliver order]

    U1 --> B1 --> D1
    B1 --> U2
    U2 --> B2 --> D2
    B2 --> U3
    U3 --> B3
    B3 --> B4 --> D3
    B4 --> U4
    U4 --> B5 --> D4
    B5 --> B6 --> D4
    B6 --> U5
    U5 --> U6
    U6 --> B7 --> D5
    B7 --> B8
    B8 --> U7
    U7 --> B9 --> D6
    B9 --> B10
    B10 --> D5
    B10 --> B11 --> D5
    B11 --> B12 --> P1
    P1 --> P2
    P2 -->|yes| B13
    P2 -->|yes| P3 --> P4 --> P5 --> B13
    P5 --> P6 --> B13
    B13 --> D7
    D7 --> U8

    %% Rejection paths
    B3 -. invalid customization .-> R1[Reject request]
    B5 -. not eligible for direct checkout .-> R2[Hide from checkout or reject request]
    B6 -. invalid pricing input .-> R3[Reject pricing request]
    B9 -. invalid or failed payment .-> R4[Do not confirm order]
    B12 -. transmission failed .-> R5[Retry without duplicate handoff]
    P2 -->|no| R6[Mark provider rejection]
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

## Direct Checkout Eligibility

Before pricing or checkout, the backend must verify that every product, kit, and
design configuration is eligible for direct checkout:

1. Product or kit is active in the public catalog
2. Provider availability for the current catalog period is compatible with sale
3. Selected material, size, finish, quantity, and template fields are valid
4. Backend pricing rules can calculate the final amount deterministically
5. No manual quote, provider confirmation, unsupported file review, or custom
   production decision is required

If any item fails these checks, checkout must not be initialized for that item.

## Order Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> confirmed: verified payment
    confirmed --> sent_to_provider: provider payload sent
    sent_to_provider --> accepted: provider accepts
    sent_to_provider --> cancelled: provider rejects
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
notifications, and order tracking. Relieves de Colombia acts as the
manufacturing provider and does not contact the customer directly in the MVP.

The carrier QR scan is the canonical trigger for moving an accepted order from
`ready_for_pickup` to `shipped`, once the QR mechanism is technically validated
with the selected carrier. Until that validation is complete, an operator may
record the equivalent shipment event without changing the status lifecycle.

Customer cancellation after payment is a request, not an automatic mutation.
The approval rule depends on the order state and the cancellation/refund policy
agreed with Relieves. The customer must see the applicable terms before payment.

## Planning Documents
- `docs/planning/foundation.md`
- `docs/planning/catalog.md`
- `docs/planning/kits.md`
- `docs/planning/templates-designs.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
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
