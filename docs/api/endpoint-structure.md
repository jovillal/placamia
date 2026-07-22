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
| Templates | `/api/v1/templates` | Design bases and template fields. | Implemented |
| Designs | `/api/v1/designs` | Customized design instances created from templates. | Implemented |
| Pricing | `/api/v1/pricing` | Backend-calculated quotes and pricing validation. | Partially implemented |
| Orders | `/api/v1/orders` | Draft orders, confirmed orders, and order tracking. | Partially implemented |
| Payments | `/api/v1/payments` | Payment initialization and payment confirmation/webhooks. | Partially implemented |
| Provider | `/api/v1/provider` | Admin-ingested provider fulfillment and operational events. | Partially implemented |
| Admin | `/api/v1/admin` | Authorized administrative changes and review workflows. | Planned |

Provider, production, shipment, delivery, and cancellation review behavior are
partially implemented through domain-local endpoints protected by admin
authorization. Broader administrative management surfaces remain reserved for
`/api/v1/admin/...` and must be scoped by a planning document and issue before
implementation.

## Admin / Operator Path Grouping

Path A uses a hybrid grouping rule:

- Use domain-local paths for narrowly scoped operational mutations tied to one
  resource, such as provider fulfillment events or order cancellation review.
- Use `/api/v1/admin/...` for broader admin management surfaces such as catalog
  maintenance, pricing table maintenance, users, dashboards, or cross-resource
  review queues.
- Existing domain-local admin/operator-like endpoints should not be renamed
  into `/api/v1/admin/...` without a dedicated compatibility issue.
- Admin/operator mutations must document authorization and audit behavior in
  their FastAPI route metadata, docstrings, and planning docs.

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
| `GET` | `/api/v1/catalog/kits` | Catalog | Public | `{ "data": KitRead[] }` with customer-safe product summaries |
| `GET` | `/api/v1/catalog/kits/{kit_id}` | Catalog | Public | Direct `KitRead` with customer-safe active contents |
| `GET` | `/api/v1/catalog/products` | Catalog | Public | `{ "data": ProductRead[], "meta": pagination }` |
| `GET` | `/api/v1/catalog/products/{product_id}` | Catalog | Public | `ProductRead` object |
| `GET` | `/api/v1/templates` | Templates | Public | `{ "data": TemplateSummaryRead[] }` |
| `GET` | `/api/v1/templates/{template_id}` | Templates | Public | `TemplateDetailRead` object with active fields |
| `POST` | `/api/v1/designs` | Designs | Required | `DesignRead` object |
| `GET` | `/api/v1/designs/{design_id}` | Designs | Required | Owner-scoped `DesignRead` object |
| `POST` | `/api/v1/pricing/quotes` | Pricing | Public for Product/Kit; required for Design | Direct discriminated Product, Kit, or Design pricing quote |
| `POST` | `/api/v1/orders` | Orders | Required | `OrderRead` object |
| `GET` | `/api/v1/orders` | Orders | Required | `{ "data": OrderSummaryRead[], "meta": OrderListMeta }` |
| `GET` | `/api/v1/orders/{order_id}` | Orders | Required | Owner-scoped `OrderDetailRead` with immutable purchased-item snapshots |
| `GET` | `/api/v1/orders/{order_id}/status` | Orders | Required | `OrderStatusRead` object |
| `POST` | `/api/v1/orders/{order_id}/cancellation-request` | Orders | Required owner | `OrderCancellationResponse` object |
| `POST` | `/api/v1/orders/{order_id}/cancellation-request/approve` | Orders | Admin | `OrderCancellationResponse` object |
| `POST` | `/api/v1/orders/{order_id}/cancellation-request/reject` | Orders | Admin | `OrderCancellationResponse` object |
| `POST` | `/api/v1/payments` | Payments | Required owner | `{ "data": PaymentInitializationData }` |
| `POST` | `/api/v1/payments/webhook` | Payments | Signed provider webhook | `PaymentWebhookResponse` object |
| `POST` | `/api/v1/provider/orders/{order_id}/acceptance` | Provider | Admin | `ProviderAcceptanceDecisionResponse` object |
| `POST` | `/api/v1/provider/orders/{order_id}/production-progress` | Provider | Admin | `ProviderProductionProgressResponse` object |
| `POST` | `/api/v1/provider/orders/{order_id}/shipment` | Provider | Admin | `ProviderShipmentResponse` object |
| `POST` | `/api/v1/provider/orders/{order_id}/delivery` | Provider | Admin | `ProviderDeliveryResponse` object |

The demo Bruno collection in `bruno/placamia-api` is intentionally partial and
should be updated by endpoint implementation issues when manual demo coverage
is needed.

## Reserved And Continuing MVP Endpoint Groups

The following groups are reserved by the MVP flow and planning documents. Some
already have partial implementations, but further endpoints must still be
scoped by planning docs and implementation issues:

| Group | Expected Path Prefix | Flow Alignment |
| --- | --- | --- |
| Templates | `/api/v1/templates` | User selects a template. |
| Designs | `/api/v1/designs` | Backend validates customization and creates a design. |
| Pricing | `/api/v1/pricing` | Backend calculates pricing from trusted catalog and rules data. |
| Orders | `/api/v1/orders` | Backend creates draft orders and exposes order tracking. |
| Payments | `/api/v1/payments` | Backend initializes payment and verifies payment confirmation. |
| Admin | `/api/v1/admin` | Admin-only catalog, pricing, order, and audit workflows. |
| Provider | `/api/v1/provider` | Admin-ingested provider fulfillment events for the MVP domain-local path. |

## Scope Notes

This document records the implemented and reserved API structure. Runtime
changes remain scoped by their planning documents and implementation issues.
