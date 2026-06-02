# Catalog Flow

## Purpose

Define how users browse and retrieve catalog data.

This is a read-only flow that exposes products, categories, and kits.

For the direct-checkout MVP path, the public catalog must expose only items that
are active and safe to present for the current catalog period. A manufacturing
provider does not need real-time inventory sync for MVP; provider availability
may be updated by a weekly operational process and reflected in backend catalog
data.

## Flow Diagram

```mermaid
flowchart TD
    O1[PlacamIA sends weekly availability form] --> P1[Provider reports availability]
    P1 --> B0[Operator updates catalog availability]
    B0 --> D0[(Catalog availability)]

    U1[User opens app] --> U2[User browses catalog]

    U2 --> B1[Fetch categories]
    B1 --> D1[(Category data)]
    D1 --> B2[Return categories]

    U2 --> B3[Fetch products]
    B3 --> D2[(Product data + availability)]
    D2 --> B4[Return products]

    U2 --> B5[Fetch kits]
    B5 --> D3[(Kit data + active contents)]
    D3 --> B6[Return kits]

    D0 --> B3
    D0 --> B5
    B2 --> U2
    B4 --> U2
    B6 --> U2

    B3 -. inactive or unavailable .-> R1[Do not expose product as purchasable]
    B5 -. no active purchasable contents .-> R2[Apply documented kit visibility rule]
```

## Constraints
- Catalog is public (no authentication required)
- Only active products must be returned
- Public catalog must not present an item as directly purchasable unless it is
  active, backend-priceable, and compatible with the assigned provider's
  availability state
- Weekly provider availability is a soft operational input, not exact inventory
  reservation
- No write operations allowed
- Provider availability updates are not customer-facing writes and must be
  handled through admin/operator scope when implemented

## Related Planning Docs
- `docs/planning/catalog.md`
- `docs/planning/kits.md`
- `docs/planning/provider.md`

## Security Notes

- Do not expose internal fields
- Validate query parameters
- Prevent data leakage
- Do not expose inactive, unavailable, or manual-quote-only products as direct
  checkout items
