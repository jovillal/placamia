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

| Product/Family | Classification | Reason | Required Variables | Notes |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## Kit Decisions

| Kit | Classification | Required Contents | Quantity Rules | Notes |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## Open Questions

-

## Implementation Impact

- Catalog changes:
- Pricing changes:
- Checkout eligibility changes:
- Seed data changes:
