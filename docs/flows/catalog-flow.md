# Catalog Flow

## Purpose

Define how users browse and retrieve catalog data.

This is a read-only flow that exposes products, categories, and kits.

## Flow Diagram

```mermaid
flowchart TD
    U1[User opens app] --> U2[User browses catalog]

    U2 --> B1[Fetch categories]
    B1 --> D1[(Category data)]
    D1 --> B2[Return categories]

    U2 --> B3[Fetch products]
    B3 --> D2[(Product data)]
    D2 --> B4[Return products]

    U2 --> B5[Fetch kits]
    B5 --> D3[(Kit data)]
    D3 --> B6[Return kits]

    B2 --> U2
    B4 --> U2
    B6 --> U2
```

## Constraints
- Catalog is public (no authentication required)
- Only active products must be returned
- No write operations allowed

## Related Planning Docs
- `docs/planning/catalog.md`

## Security Notes

- Do not expose internal fields
- Validate query parameters
- Prevent data leakage