# Product Classification Validation

## Purpose

Classify each product, product family, and kit for Path A direct checkout.

Findings may name the validation partner that provided them. Classification
states and implementation decisions must remain provider-neutral.

## Provider

- Validation partner:
- Date:
- Owner/contact:
- PlacamIA reviewer:

## Classification States

- `direct_checkout`: Can be sold through backend pricing and checkout.
- `made_to_order_parametrizable`: Can be sold if all variables are
  backend-priceable.
- `manual_quote_required`: Requires provider review before pricing.
- `temporarily_unavailable`: Not purchasable for the current catalog period.
- `outsourced_not_mvp_direct`: Not safe for MVP direct checkout.
- `not_supported`: Provider cannot fulfill this item.

## Product Decisions

| Product/Family | Classification | Confidence | Reason | Required Variables | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  |  | |  |

### Examples

#### Example 1 — Good Direct Checkout Candidate
Imagine a standard engraved acrylic office sign.

| Product/Family | Classification | Confidence | Reason | Required Variables | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Acrylic Office Sign | direct_checkout | High | Standardized product with known production process and deterministic pricing | width, height, material thickness, engraving type | Partner interview 2026-06-15 | No provider review required |

Interpretation:

Customer selects options.
Backend can calculate price.
Safe for checkout.

Exactly what Path A wants.

#### Example 2 — Made To Order but Still Checkout Eligible

Imagine an industrial machine identification plate.

| Product/Family | Classification | Confidence | Reason | Required Variables | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Industrial Identification Plate | made_to_order_parametrizable | Medium | Produced after purchase but variables are standardized and priceable | material, dimensions, mounting holes, engraving lines | Operations meeting 2026-06-15 | Need confirmation of maximum supported dimensions |

Interpretation:

Not stocked.
Produced on demand.
Still deterministic.

Path A can probably sell it.

#### Example 3 — Manual Quote Required

Imagine a custom safety board with arbitrary layouts.

| Product/Family | Classification | Confidence | Reason | Required Variables | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Custom Plant Safety Board | manual_quote_required | High | Requires design review and production feasibility assessment before pricing | N/A | Partner interview 2026-06-15 | Future RFQ candidate |

Interpretation:

Human review needed.
Price cannot be determined safely.
Excluded from direct checkout.

#### Example 4 — Outsourced
| Product/Family | Classification | Confidence | Reason | Required Variables | Evidence | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Reflective Highway Sign | outsourced_not_mvp_direct | Medium | Fulfilled through third-party provider with variable lead times | N/A | Operations discussion | Reevaluate after MVP |

Interpretation:

Provider might sell it.
PlacamIA should not sell it in Path A.

## Kit Decisions

| Kit | Classification | Required Contents | Quantity Rules | Notes |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

### Example Kit

| Kit | Classification | Required Contents | Quantity Rules | Notes |
| --- | --- | --- | --- | --- |
| Fire Extinguisher Safety Kit | direct_checkout | Fire Extinguisher Sign, Evacuation Marker, Inspection Label | Fixed quantities | All contents individually approved for direct checkout |

## Open Questions

-

## Implementation Impact

- Catalog changes:
- Pricing changes:
- Checkout eligibility changes:
- Seed data changes:
