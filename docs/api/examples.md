# API Examples

## Health

```http
GET /api/v1/health/
```

```json
{
  "status": "ok"
}
```

## Current User

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
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

## Catalog Categories

```http
GET /api/v1/catalog/categories
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

## Catalog Products

```http
GET /api/v1/catalog/products
```

```json
{
  "data": [
    {
      "id": 1,
      "name": "Emergency exit sign",
      "description": "Standard sign for marking emergency exits.",
      "category_id": 1,
      "base_price": "18000.00"
    }
  ]
}
```

## Authentication Error

```json
{
  "detail": "Invalid authentication credentials"
}
```
