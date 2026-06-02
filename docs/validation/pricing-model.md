# Pricing Model Validation

## Purpose

Validate which products and kits can be priced deterministically by the
backend.

Findings may name the validation partner that provided them. Pricing structures
and implementation decisions must remain provider-neutral.

## Provider

- Validation partner:
- Date:
- Pricing owner:
- PlacamIA reviewer:

## Pricing Inputs

| Input | Required? | Allowed Values / Range | Source of Truth | Notes |
| --- | --- | --- | --- | --- |
| product/family | yes |  | backend catalog |  |
| material |  |  |  |  |
| size |  |  |  |  |
| finish |  |  |  |  |
| quantity |  |  |  |  |
| design options |  |  |  |  |

## Pricing Rules

| Product/Family | Base Rule | Adjustments | Min Qty | Max Qty | Notes |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

## Kit Pricing

| Kit | Pricing Method | Fixed/Editable Quantities | Notes |
| --- | --- | --- | --- |
|  |  |  |  |

## Rejection Rules

Backend pricing must reject:

- inactive products
- unavailable products
- manual-quote-only products
- invalid material/size/finish
- unsupported quantity
- frontend-supplied totals

## Open Questions

-

## Implementation Impact

- Pricing rules:
- Pricing endpoint:
- Tests:
