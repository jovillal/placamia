# PlacamIA Main Flow

## Purpose

This document defines the MVP system flow for PlacamIA.

It is the source of truth for the automated diagram. The visual diagram should
be generated from this flow, not maintained manually.

## Flow Diagram

```mermaid
flowchart TD
    %% User lane
    U1[User browses catalog]
    U2[User selects template]
    U3[User customizes design]
    U4[User requests pricing]
    U5[User confirms checkout]
    U6[User completes payment]
    U7[User tracks order]

    %% Backend lane
    B1[Fetch categories, products, kits]
    B2[Return template and fields]
    B3[Validate customization]
    B4[Create design]
    B5[Calculate backend pricing]
    B6[Create draft order]
    B7[Initialize payment]
    B8[Verify payment webhook]
    B9[Confirm order]
    B10[Prepare provider payload]
    B11[Send order to provider]
    B12[Update order status]

    %% Database lane
    D1[(Catalog data)]
    D2[(Templates)]
    D3[(Design)]
    D4[(Pricing rules)]
    D5[(Order + OrderItems)]
    D6[(Payment)]
    D7[(Order status)]

    %% Provider lane
    P1[Provider receives order]
    P2[Provider accepts or rejects]
    P3[Manufacture order]
    P4[Ship order]

    U1 --> B1 --> D1
    B1 --> U2
    U2 --> B2 --> D2
    B2 --> U3
    U3 --> B3
    B3 --> B4 --> D3
    B4 --> U4
    U4 --> B5 --> D4
    B5 --> U5
    U5 --> B6 --> D5
    B6 --> B7
    B7 --> U6
    U6 --> B8 --> D6
    B8 --> B9
    B9 --> D5
    B9 --> B10 --> D5
    B10 --> B11 --> P1
    P1 --> P2
    P2 --> B12
    P2 --> P3 --> P4 --> B12
    B12 --> D7
    D7 --> U7

    %% Rejection paths
    B3 -. invalid customization .-> R1[Reject request]
    B5 -. invalid pricing input .-> R2[Reject pricing request]
    B8 -. invalid or failed payment .-> R3[Do not confirm order]
    P2 -. rejected .-> R4[Mark provider rejection]
```

## Order Status Lifecycle

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> confirmed: verified payment
    confirmed --> sent_to_provider: provider payload sent
    sent_to_provider --> accepted: provider accepts
    sent_to_provider --> cancelled: provider rejects
    accepted --> in_production
    in_production --> shipped
    shipped --> delivered
    draft --> cancelled: user/payment failure/admin cancel
```

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

## Rule

Manual diagrams are optional presentation artifacts only.

The Mermaid diagrams in this file are the canonical flow representation.
