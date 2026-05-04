# Endpoint Structure

## Purpose

This document defines the standard API grouping and endpoint inventory for
PlacamIA.

It must stay aligned with `docs/planning/foundation.md`,
`docs/flows/main-flow.md`, and the FastAPI routes under `apps/api/app/api`.

## Base Prefix

All API endpoints must use:

```text
/api/v1
```

The current application composes this prefix from:

- `/api` in `apps/api/app/api/router.py`
- `/v1` in `apps/api/app/api/v1/router.py`

## Grouping Standard

Use these top-level groups for MVP API routes:

| Group | Path Prefix | Purpose | MVP Status |
| --- | --- | --- | --- |
| Health | `/api/v1/health` | Runtime health checks for the backend. | Implemented |
| Auth | `/api/v1/auth` | Authenticated user context and auth-related endpoints. | Implemented |
| Catalog | `/api/v1/catalog` | Categories, products, and kits that users can browse. | Partially implemented |
| Templates | `/api/v1/templates` | Design bases and template fields. | Planned |
| Designs | `/api/v1/designs` | Customized design instances created from templates. | Planned |
| Pricing | `/api/v1/pricing` | Backend-calculated quotes and pricing validation. | Planned |
| Orders | `/api/v1/orders` | Draft orders, confirmed orders, and order tracking. | Planned |
| Payments | `/api/v1/payments` | Payment initialization and payment confirmation/webhooks. | Planned |
| Admin | `/api/v1/admin` | Authorized administrative changes and review workflows. | Planned |

Provider, production, and shipment behavior remain part of the MVP flow, but
public endpoint paths for those concerns are not implemented yet. Add them only
when a planning document and issue define the required API contract.

## Naming Conventions

- Use plural resource names for collections.
- Keep paths lowercase.
- Use `snake_case` for path parameter names, query parameters, and JSON fields.
- Keep endpoint names stable and aligned with planning documents.
- Avoid action verbs in paths unless the domain action cannot be expressed by an
  HTTP method and resource name.
- Keep route handlers thin; route handlers validate input, call services, and
  serialize responses.

## Request Conventions

- Use Pydantic schemas for request bodies.
- Use path parameters for required identifiers, such as `{order_id}`.
- Use query parameters for optional list controls.
- Do not accept frontend-supplied ownership claims as authorization.
- Do not accept frontend-calculated prices as final pricing.

## Response Conventions

Follow `docs/api/api-style.md` for the full response contract.

In short:

- health endpoints may return direct status payloads
- single-resource endpoints return the resource object directly
- collection endpoints return an object with a `data` array
- errors use FastAPI's `detail` field

## Implemented Endpoint Inventory

The current implemented API endpoints are:

| Method | Path | Group | Authentication | Response Shape |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/health/` | Health | Public | `{ "status": "ok" }` |
| `GET` | `/api/v1/auth/me` | Auth | Required | `UserRead` object |
| `GET` | `/api/v1/catalog/categories` | Catalog | Public | `{ "data": CategoryRead[] }` |

## Planned MVP Endpoint Groups

The following groups are reserved by the MVP flow and planning documents, but
their endpoints are not implemented by this standardization task:

| Group | Expected Path Prefix | Flow Alignment |
| --- | --- | --- |
| Catalog products | `/api/v1/catalog/products` | User browses catalog products. |
| Catalog kits | `/api/v1/catalog/kits` | User browses kit bundles. |
| Templates | `/api/v1/templates` | User selects a template. |
| Designs | `/api/v1/designs` | Backend validates customization and creates a design. |
| Pricing | `/api/v1/pricing` | Backend calculates pricing from trusted catalog and rules data. |
| Orders | `/api/v1/orders` | Backend creates draft orders and exposes order tracking. |
| Payments | `/api/v1/payments` | Backend initializes payment and verifies payment confirmation. |
| Admin | `/api/v1/admin` | Admin-only catalog, pricing, order, and audit workflows. |

## Scope Notes

This document standardizes API documentation only.

No new endpoints are introduced by this task, and no runtime API behavior is
changed.
