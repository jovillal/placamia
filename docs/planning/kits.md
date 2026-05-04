# Kits

## Goal

Allow users to browse curated bundles of catalog products.

Kits are sellable bundles that reduce friction for common signage needs while
remaining read-only in the MVP customer catalog.

## Scope

- Kit model
- KitItem model
- Kit-to-product relationships
- Public kit listing endpoint
- Active product visibility rules for kit contents

## Related Domain Concepts

- Kit = bundle of products
- KitItem = product entry inside a kit with quantity metadata
- Product = sellable item that may appear independently or inside a kit

## Endpoints

Planned:

- GET /api/v1/catalog/kits

Future issue required:

- GET /api/v1/catalog/kits/{kit_id}

## Child Issues

Planned:

- #24 Create Kit and KitItem models, migrations, and tests
- #25 Create GET kits endpoint with tests

## Future Issues

- Future issue required: create kit detail endpoint with tests
- Future issue required: define inactive product behavior inside kits
- Future issue required: define kit pricing interaction with pricing rules

## Constraints

- Customer-facing kit endpoints are public.
- Kit endpoints are read-only in the MVP.
- Kits must not expose inactive products as available for purchase.
- Admin kit creation/update/delete belongs to a future admin/backoffice scope.
- Pricing calculations for kits belong to pricing scope, not catalog browsing.

## Security Considerations

- Do not expose internal fields.
- Do not expose inactive products as available kit contents.
- Validate kit identifiers and any future query parameters.
- Do not accept frontend-provided prices or discounts.

## Done When

- Kit and KitItem data is modeled and migrated.
- Kits can be browsed through the public catalog.
- Kit responses include only documented public fields.
- Inactive products are not exposed as available kit contents.
- Kit endpoints are tested.
