# Kits

## Goal

Allow users to browse curated bundles of catalog products.

Kits are sellable bundles that reduce friction for common signage needs while
remaining read-only in the MVP customer catalog.

For the direct-checkout MVP path, a kit may be purchasable only when every
required item in the kit is active, compatible with provider adapter boundary
responses, and backend-priceable.

## Scope

- Kit model
- KitItem model
- Kit-to-product relationships
- Public kit listing endpoint
- Active product visibility rules for kit contents
- Direct-checkout eligibility rules for kits
- Provider adapter boundary responses for kit availability, direct-checkout
  eligibility, lead time, and fulfillment capability

## Related Domain Concepts

- Kit = bundle of products
- KitItem = product entry inside a kit with quantity metadata
- Product = sellable item that may appear independently or inside a kit
- Provider adapter boundary = backend contract used to obtain provider
  availability, direct-checkout eligibility, lead time, provider cost inputs,
  and fulfillment capability signals for kit contents
- Direct-checkout kit = active kit whose required contents are active,
  available through provider adapter responses, and deterministically priceable

## Endpoints

Implemented:

- GET /api/v1/catalog/kits

Future issue required:

- GET /api/v1/catalog/kits/{kit_id}

## Child Issues

Completed:

- #24 Create Kit and KitItem models, migrations, and tests
- #25 Create GET kits endpoint with tests
- #172 Implement approved public kit visibility and content response contract

## Future Issues

- Future issue required: create kit detail endpoint with tests
- Future issue required: define kit pricing interaction with pricing rules and
  provider cost inputs from the provider adapter boundary

## Current MVP Listing Behavior

`GET /api/v1/catalog/kits` returns active Kits only.

Current `KitItem` rows are treated as required kit contents because the model
does not yet include optional kit items.

Active Kits remain visible only when they have at least one active required
Product. Active Kits with zero active required Products are hidden from the
public catalog rather than returned with an empty `items` array.

Kit contents must not expose inactive Products as available contents. Inactive
Product contents are omitted from the customer-visible kit contents and cannot
make the Kit purchasable. If all required Product contents are inactive, the Kit
is hidden.

Unavailable, manual-quote-only, or non-priceable required Product contents must
not be silently omitted from a visible Kit because omission would change what
the Kit is. A Kit with at least one active required Product remains visible,
but its kit-level eligibility fields must report that the Kit is not directly
purchasable when any required content is unavailable, manual-quote-only,
otherwise ineligible, or not backend-priceable.

Public Kit item responses must include customer-safe Product summaries rather
than only a `product_id`, so customers can understand what the bundle contains.
The summary must not expose provider cost, provider assignment, raw provider
payloads, internal eligibility inputs, or inactive-product internals.

Public Kit content shape:

- product_id
- product name
- customer-safe product description
- category_id
- quantity

Public Kit direct-checkout signals:

- `availability_state`
- `direct_checkout_eligible`
- `eligibility_reason`
- `production_lead_time_days`
- `dispatch_lead_time_days`

These fields are backend-derived through the provider adapter boundary.
Frontend-supplied kit contents, availability, eligibility, lead time, provider
cost, or provider capability claims must not influence them.

Kit direct checkout follows the catalog availability state contract in
`docs/planning/catalog.md`. A Kit is eligible only when:

- the Kit is active
- every required KitItem product is active
- every required KitItem product is compatible with provider adapter
  availability and direct-checkout eligibility
- every required KitItem product is backend-priceable
- the Kit itself is compatible with provider adapter availability and
  direct-checkout eligibility

Implementation is tracked by #110 and was refined by #172.

## Constraints

- Customer-facing kit endpoints are public.
- Kit endpoints are read-only in the MVP.
- Kits must not expose inactive products as available for purchase.
- Kits must not be directly purchasable when required contents are inactive,
  unavailable, manual-quote-only, or not backend-priceable.
- Kits with zero active required contents must be hidden.
- Unavailable required contents must not be omitted from visible Kits; they must
  make the Kit visible but not directly purchasable with a backend-derived
  eligibility reason.
- Kit availability, direct-checkout eligibility, lead time, and provider
  capability signals must come through the backend provider adapter boundary,
  starting with a local/mock adapter for MVP backend development.
- Admin kit creation/update/delete belongs to a future admin/backoffice scope.
- Pricing calculations for kits belong to pricing scope, not catalog browsing.
- Partner validation may update adapter fixtures and seed data later, but kit
  eligibility architecture must not wait for a real-provider integration.

## Security Considerations

- Do not expose internal fields.
- Do not expose inactive products as available kit contents.
- Validate kit identifiers and any future query parameters.
- Do not accept frontend-provided prices or discounts.
- Do not allow frontend-supplied kit contents, provider assignment,
  availability, eligibility, lead time, provider cost, or fulfillment capability
  claims to influence checkout eligibility.

## Done When

- Kit and KitItem data is modeled and migrated.
- Kits can be browsed through the public catalog.
- Kit responses include only documented public fields.
- Inactive products are not exposed as available kit contents.
- Kit checkout eligibility follows active product, provider adapter boundary,
  and backend pricing rules.
- Kits with unavailable, manual-quote-only, or non-priceable required contents
  are visible only when at least one required Product is active, and are
  returned as not directly purchasable instead of having contents silently
  omitted.
- Public kit contents include customer-safe Product summaries and exclude
  provider/internal fields.
- Kit endpoints are tested.
- Kit visibility and purchasability refinements from #87 are documented.
