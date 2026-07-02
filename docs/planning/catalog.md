# Catalog

## Goal

Allow users to browse a curated catalog of products and kits.

This is the entry point of the MVP and must be simple, fast, and aligned with the goal of reducing friction in selecting required signage.

The MVP follows Path A: catalog items may be presented for direct checkout only
when they are active, compatible with provider adapter boundary responses, and
fully priceable by backend rules.

## Scope

- Categories
- Products
- Product filters and pagination for the documented public browse parameters
- Kit browsing is related catalog behavior, but kit-specific model and endpoint
  work is tracked in `docs/planning/kits.md`
- Provider adapter boundary responses for availability, direct-checkout
  eligibility, lead time, and provider capability visibility
- Backend-owned provider eligibility/assignment data for direct-checkout items

## Related Domain Concepts

- Product = sellable item
- Kit = bundle of products; see `docs/planning/kits.md`
- Category = grouping for browsing
- Provider = configured manufacturing partner that can fulfill eligible catalog
  items
- Provider adapter boundary = backend contract used to obtain provider
  availability, direct-checkout eligibility, lead time, and fulfillment
  capability signals
- Provider availability = soft operational signal from the provider adapter for
  the current catalog period, not exact inventory reservation
- Direct-checkout eligibility = backend-derived state based on active catalog
  data, provider adapter responses, provider assignment, and deterministic
  pricing

## Related Validation Docs

- `docs/planning/provider.md`
- `docs/planning/provider-adapter-contract.md`
- `docs/validation/product-classification.md`
- `docs/validation/availability-model.md`
- `docs/validation/provider-onboarding-checklist.md`

## Endpoints

Implemented:

- GET /api/v1/catalog/categories
- GET /api/v1/catalog/products
- GET /api/v1/catalog/products/{product_id}
- GET /api/v1/catalog/kits

`GET /api/v1/catalog/products` supports only these optional query parameters:

- `category_id`: positive integer category filter.
- `page`: positive integer page number; defaults to `1`.
- `page_size`: positive integer page size; defaults to `20` and is capped at
  `50`.

Unknown query parameters are rejected. Product listing applies stable ordering
by `name ASC, id ASC` before pagination and returns pagination metadata:
`page`, `page_size`, `total_items`, and `total_pages`.

## Direct-Checkout Eligibility Contract

Catalog visibility and direct-checkout purchasability are separate concepts.
An item may be visible in the catalog while not being eligible for direct
checkout.

The public catalog contract uses these backend-derived fields for products and
kits:

- `availability_state`
- `direct_checkout_eligible`
- `eligibility_reason`
- `production_lead_time_days`
- `dispatch_lead_time_days`

These fields are derived by the backend through the provider adapter boundary.
They are not accepted from the frontend and must not be treated as customer
price inputs. Provider pricing output remains provider-owned base
cost/capability data; PlacamIA backend pricing services calculate customer
price, margin, taxes/fees, discounts, and checkout totals.

Initial availability states:

| State | Direct checkout behavior |
| --- | --- |
| `available` | Eligible only when the product or kit is active, backend-priceable, and adapter-capable. |
| `made_to_order_parametrizable` | Eligible only when the requested configuration is supported and backend-priceable. |
| `temporarily_unavailable` | Not purchasable. |
| `manual_quote_required` | Not purchasable in MVP checkout. Future RFQ/manual quote flow required. |
| `outsourced_not_mvp_direct` | Not purchasable in MVP checkout. |

Future implementation issues:

- #108 Implement local/mock provider adapter availability fixtures.
- #109 Add product listing and detail eligibility fields.
- #110 Add kit direct-checkout eligibility behavior.
- #111 Update MVP seed data after validation findings.

## Child Issues

Completed:

- #15 Create Category model, migration, and tests
- #16 Create Product model, migration, and tests
- #17 Add catalog seed data
- #18 Create GET categories endpoint with tests
- #19 Create GET products endpoint with tests
- #20 Create GET product detail endpoint with tests
- #77 GET catalog products with filtering and pagination

Related Kits milestone:

- #24 Create Kit and KitItem models, migrations, and tests
- #25 Create GET kits endpoint with tests

Related Phase 2 follow-up:

- #87 Define kit public visibility rules

Related Security milestone:

- #52 Define inactive product behavior for customer catalog and ordering

## Constraints

- Catalog endpoints are public (no auth required)
- Only active products should be visible
- Public catalog must not expose unavailable, manual-quote-only, or
  non-priceable products as directly purchasable
- Provider availability, direct-checkout eligibility, and lead time must come
  through the backend provider adapter boundary, starting with a local/mock
  adapter for MVP backend development
- Provider availability is a soft operational input and does not imply exact
  inventory reservation
- Customer-facing catalog behavior must not allow the frontend to choose,
  spoof, or override provider assignment, availability, eligibility, or lead
  time
- Partner validation may update adapter fixtures and seed data later, but
  catalog architecture must not wait for a real-provider integration
- No write operations in MVP (admin handled later)
- Product listing filters and pagination are limited to the documented
  `category_id`, `page`, and `page_size` query parameters. They must not let
  clients choose provider, availability, direct-checkout eligibility, lead
  time, price, or arbitrary sorting.

## Security Considerations

- Do not expose internal fields
- Validate all query parameters
- Prevent data leakage
- Return inactive products as absent from public catalog responses
- Return unavailable or manual-quote-only products as absent from direct
  checkout responses unless a future documented flow defines a non-checkout
  presentation mode
- Ignore or reject frontend-supplied provider availability, eligibility, lead
  time, provider assignment, or capability claims

## Done When

- Categories and products can be browsed
- Kits can be browsed through the public catalog
- Product detail can be retrieved for active products
- Inactive products are excluded from public catalog responses
- Unavailable and manual-quote-only products are not exposed as directly
  purchasable
- Product filters and pagination use the documented `category_id`, `page`, and
  `page_size` contract
- Kit public visibility refinements are handled by #87 when phase-2/mobile UX
  needs require them
- All catalog endpoints are tested
