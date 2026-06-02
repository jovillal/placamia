# Availability Model Validation

## Purpose

Define provider availability states and how they affect catalog and checkout.

Findings may name the validation partner that provided them. Availability
states and implementation decisions must remain provider-neutral.

## Provider

- Validation partner:
- Date:
- Availability owner:
- Update cadence:

## Availability States

| State | Meaning | Catalog Behavior | Checkout Behavior |
| --- | --- | --- | --- |
| `available` | Provider can fulfill this item. | visible | purchasable |
| `made_to_order_parametrizable` | Provider can fulfill if backend-priced variables are valid. | visible | purchasable |
| `temporarily_unavailable` | Provider cannot fulfill during this period. | visible or hidden TBD | not purchasable |
| `manual_quote_required` | Provider must review before pricing. | visible or hidden TBD | not purchasable |
| `outsourced_not_mvp_direct` | Fulfillment depends on external party. | hidden or not purchasable | not purchasable |

## Product Availability

| Product/Family | State | Effective From | Effective Until | Notes |
| --- | --- | --- | --- | --- |
|  |  |  |  |  |

## Kit Availability

| Kit | State | Blocking Contents | Notes |
| --- | --- | --- | --- |
|  |  |  |  |

## Update Process

- Who sends update request:
- Who answers:
- Format:
- Cadence:
- Escalation path:

## Open Questions

-

## Implementation Impact

- Provider availability model:
- Catalog response:
- Checkout eligibility:
- Tests:
