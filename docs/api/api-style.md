# API Style Guide

## Purpose

This guide defines the API naming, request, response, and error conventions for
PlacamIA endpoints.

It applies to the FastAPI backend under `apps/api` and must be followed for all
new or changed API behavior.

## Base Path

All public API endpoints must be served under:

```text
/api/v1
```

The `/api` prefix is defined by `apps/api/app/api/router.py`. The `/v1` prefix is
defined by `apps/api/app/api/v1/router.py`.

Do not introduce another version prefix until a future planning document
explicitly defines versioning behavior.

## Resource Naming

- Use lowercase URL path segments.
- Use plural nouns for resource collections.
- Use stable resource names from the planning documents.
- Use nested paths only when the child resource is scoped by the parent.
- Use path parameters for resource identity.
- Use query parameters for filtering, pagination, sorting, and optional views.
- Use `snake_case` for JSON field names and query parameter names.
- Do not include verbs in resource paths when an HTTP method already expresses
  the action.

Examples:

```text
GET /api/v1/catalog/categories
GET /api/v1/templates/{template_id}
POST /api/v1/designs
POST /api/v1/pricing/quotes
GET /api/v1/orders/{order_id}
```

Avoid:

```text
GET /api/v1/getCategories
POST /api/v1/orders/create
GET /api/v1/orderStatus
```

## Endpoint Groups

Endpoint groups are documented in `docs/api/endpoint-structure.md`.

Use the same group names in FastAPI tags so endpoints are discoverable in
`/docs`.

## Request Structure

All request bodies must be JSON and validated with explicit Pydantic schemas.

Routes must not accept unvalidated dictionaries for business input. Validation
belongs at the API boundary, and business decisions belong in service classes.

Use:

- path parameters for required resource identifiers
- query parameters for optional list controls
- request bodies for create, update, checkout, payment, and pricing input
- backend-derived identity for protected resources

Do not accept `user_id`, `role`, `is_admin`, ownership fields, or
frontend-calculated prices as proof of authorization or final pricing.

## Response Structure

Responses must be deterministic and documented through FastAPI response models
when a stable schema exists.

Use these conventions:

- Health and operational endpoints may return a small direct status payload.
- Single-resource endpoints return the resource object directly.
- Collection endpoints return an object with a `data` array.
- Future paginated collection endpoints should include pagination metadata
  alongside `data`.
- Mutation endpoints should return the created or updated resource when useful,
  or a minimal status payload when no resource representation is needed.

Current examples:

```json
{
  "status": "ok"
}
```

```json
{
  "id": 1,
  "email": "ada@example.com",
  "full_name": "Ada Lovelace",
  "is_active": true,
  "is_admin": false,
  "created_at": "2026-04-29T00:00:00Z",
  "updated_at": "2026-04-29T00:00:00Z"
}
```

```json
{
  "data": [
    {
      "id": 1,
      "name": "Emergency",
      "description": null,
      "created_at": "2026-04-18T00:00:00Z",
      "updated_at": "2026-04-18T00:00:00Z"
    }
  ]
}
```

## Error Structure

FastAPI errors use the `detail` field. PlacamIA documents and tests API errors
against that structure.

Simple error example:

```json
{
  "detail": "Invalid authentication credentials"
}
```

Validation error example:

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "name"],
      "msg": "Field required",
      "input": {}
    }
  ]
}
```

Routes must not expose stack traces, secrets, tokens, payment details, database
connection data, or internal exception messages.

## Status Codes

Use standard HTTP status codes consistently:

- `200 OK` for successful reads and updates
- `201 Created` for successful resource creation
- `204 No Content` for successful deletes or side-effect actions with no body
- `400 Bad Request` for malformed or invalid business requests
- `401 Unauthorized` for missing or invalid authentication
- `403 Forbidden` for authenticated users without required authorization
- `404 Not Found` for missing resources or resources hidden by authorization
- `409 Conflict` for state conflicts
- `422 Unprocessable Entity` for request validation errors raised by FastAPI
- `500 Internal Server Error` for unexpected server failures

## Security Rules

The backend is the source of truth for authorization, pricing, checkout, orders,
payments, and admin behavior.

API implementations must:

- derive the current user from the authenticated request
- enforce admin authorization on admin endpoints
- calculate pricing on the backend
- reject inactive or invalid catalog inputs
- verify payment webhooks before confirming orders
- avoid logging secrets or full payment data
- avoid mutating database state on rejected security-sensitive requests

## Documentation Rules

Each endpoint must include:

- a FastAPI summary
- a FastAPI description
- request and response schemas when applicable
- a route function docstring

When endpoint behavior changes, update this guide, the endpoint structure
inventory, and any affected planning or flow document.
