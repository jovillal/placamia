# Catalog

## Goal

Allow users to browse a curated catalog of products and kits.

This is the entry point of the MVP and must be simple, fast, and aligned with the goal of reducing friction in selecting required signage.

## Scope

- Categories
- Products
- Product filters and pagination only after a dedicated issue defines the
  supported parameters
- Kit browsing is related catalog behavior, but kit-specific model and endpoint
  work is tracked in `docs/planning/kits.md`

## Related Domain Concepts

- Product = sellable item
- Kit = bundle of products; see `docs/planning/kits.md`
- Category = grouping for browsing

## Endpoints

Implemented:

- GET /api/v1/catalog/categories
- GET /api/v1/catalog/products
- GET /api/v1/catalog/products/{product_id}
- GET /api/v1/catalog/kits

Planned:

- GET /api/v1/catalog/products with filtering and pagination

## Child Issues

Completed:

- #15 Create Category model, migration, and tests
- #16 Create Product model, migration, and tests
- #17 Add catalog seed data
- #18 Create GET categories endpoint with tests
- #19 Create GET products endpoint with tests
- #20 Create GET product detail endpoint with tests

Planned:

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
- No write operations in MVP (admin handled later)
- Product listing filters and pagination must not be added until their accepted
  query parameters and validation behavior are documented

## Security Considerations

- Do not expose internal fields
- Validate all query parameters
- Prevent data leakage
- Return inactive products as absent from public catalog responses

## Done When

- Categories and products can be browsed
- Kits can be browsed through the public catalog
- Product detail can be retrieved for active products
- Inactive products are excluded from public catalog responses
- Product filters and pagination are implemented after #77 defines the contract
- Kit public visibility refinements are handled by #87 when phase-2/mobile UX
  needs require them
- All catalog endpoints are tested
