# Kits

## Goal

Allow users to browse curated bundles of catalog products.

Kits are sellable bundles that reduce friction for common signage needs while
remaining read-only in the MVP customer catalog.

For the direct-checkout MVP path, a kit may be purchasable only when every
required item in the kit is active, compatible with current provider
availability, and backend-priceable.

## Scope

- Kit model
- KitItem model
- Kit-to-product relationships
- Public kit listing endpoint
- Active product visibility rules for kit contents
- Direct-checkout eligibility rules for kits

## Related Domain Concepts

- Kit = bundle of products
- KitItem = product entry inside a kit with quantity metadata
- Product = sellable item that may appear independently or inside a kit
- Direct-checkout kit = active kit whose required contents are active,
  available, and deterministically priceable

## Endpoints

Implemented:

- GET /api/v1/catalog/kits

Future issue required:

- GET /api/v1/catalog/kits/{kit_id}

## Child Issues

Completed:

- #24 Create Kit and KitItem models, migrations, and tests
- #25 Create GET kits endpoint with tests

## Future Issues

- Future issue required: create kit detail endpoint with tests
- #87 Define kit public visibility rules
- Future issue required: define kit pricing interaction with pricing rules

## Current MVP Listing Behavior

`GET /api/v1/catalog/kits` returns active Kits only.

Kit contents expose active Product references only. Inactive Products are
omitted from each Kit's `items` array and are not shown as available kit
contents.

Direct-checkout eligibility is stricter than public listing. A listed Kit must
not be purchasable unless its required contents are active, compatible with
current Relieves availability, and priceable by backend rules.

Current public KitItem shape:

- product_id
- quantity

Active Kits with zero active Product contents are currently returned with an
empty `items` array. Whether those Kits should be hidden, and whether kit
responses should include product summaries instead of only product identifiers,
is tracked by #87 as phase-2 work.

## Constraints

- Customer-facing kit endpoints are public.
- Kit endpoints are read-only in the MVP.
- Kits must not expose inactive products as available for purchase.
- Kits must not be directly purchasable when required contents are inactive,
  unavailable, manual-quote-only, or not backend-priceable.
- Admin kit creation/update/delete belongs to a future admin/backoffice scope.
- Pricing calculations for kits belong to pricing scope, not catalog browsing.

## Security Considerations

- Do not expose internal fields.
- Do not expose inactive products as available kit contents.
- Validate kit identifiers and any future query parameters.
- Do not accept frontend-provided prices or discounts.
- Do not allow frontend-supplied kit contents or availability to influence
  checkout eligibility.

## Done When

- Kit and KitItem data is modeled and migrated.
- Kits can be browsed through the public catalog.
- Kit responses include only documented public fields.
- Inactive products are not exposed as available kit contents.
- Kit checkout eligibility follows active product, provider availability, and
  backend pricing rules.
- Kit endpoints are tested.
- Phase-2 public visibility refinements are tracked by #87.
