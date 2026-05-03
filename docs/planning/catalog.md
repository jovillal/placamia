# Catalog Flow

## Goal

Allow users to browse a curated catalog of products and kits.

This is the entry point of the MVP and must be simple, fast, and aligned with the goal of reducing friction in selecting required signage.

## Scope

- Categories
- Products
- Kits (read-only in this phase)

## Related Domain Concepts

- Product = sellable item
- Kit = bundle of products
- Category = grouping for browsing

## Endpoints

- GET /api/v1/catalog/categories
- GET /api/v1/catalog/products
- GET /api/v1/catalog/products/{id}
- GET /api/v1/catalog/kits (future)

## Child Issues

- #15 Create Category model, migration, and tests
- #16 Create Product model, migration, and tests
- #17 Add catalog seed data
- #18 Create GET categories endpoint with tests
- #19 Create GET products endpoint with filters and tests
- #20 Create GET product detail endpoint with tests

## Constraints

- Catalog endpoints are public (no auth required)
- Only active products should be visible
- No write operations in MVP (admin handled later)

## Security Considerations

- Do not expose internal fields
- Validate all query parameters
- Prevent data leakage

## Done When

- Categories and products can be browsed
- Filters work correctly
- Only valid products are returned
- All endpoints are tested