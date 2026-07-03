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
GET /api/v1/catalog/products?category_id=1&page=1&page_size=20
```

```json
{
  "data": [
    {
      "id": 1,
      "name": "Emergency exit sign",
      "description": "Standard sign for marking emergency exits.",
      "category_id": 1,
      "base_price": "18000.00",
      "availability_state": "available",
      "direct_checkout_eligible": true,
      "eligibility_reason": null,
      "production_lead_time_days": 5,
      "dispatch_lead_time_days": 1
    }
  ],
  "meta": {
    "page": 1,
    "page_size": 20,
    "total_items": 1,
    "total_pages": 1
  }
}
```

Supported product list query parameters are `category_id`, `page`, and
`page_size` only. `page` defaults to `1`, `page_size` defaults to `20`, and
`page_size` may not exceed `50`.

## Catalog Product Detail

```http
GET /api/v1/catalog/products/1
```

```json
{
  "id": 1,
  "name": "Emergency exit sign",
  "description": "Standard sign for marking emergency exits.",
  "category_id": 1,
  "base_price": "18000.00",
  "availability_state": "available",
  "direct_checkout_eligible": true,
  "eligibility_reason": null,
  "production_lead_time_days": 5,
  "dispatch_lead_time_days": 1
}
```

## Catalog Kits

```http
GET /api/v1/catalog/kits
```

```json
{
  "data": [
    {
      "id": 1,
      "name": "Emergency evacuation kit",
      "description": "Common signage for evacuation routes.",
      "items": [
        {
          "product_id": 1,
          "name": "Emergency exit sign",
          "description": "Standard sign for marking emergency exits.",
          "category_id": 1,
          "quantity": 4
        }
      ],
      "availability_state": "available",
      "direct_checkout_eligible": true,
      "eligibility_reason": null,
      "production_lead_time_days": 5,
      "dispatch_lead_time_days": 1
    }
  ]
}
```

Kit contents include customer-safe active Product summaries. Inactive required
contents are not exposed as available contents; active unavailable,
manual-quote-only, or non-priceable required contents remain listed and make
the kit not directly purchasable through backend-derived eligibility fields.

## Pricing Preview

```http
POST /api/v1/pricing/quotes
Content-Type: application/json
```

```json
{
  "item_type": "product",
  "item_id": 1,
  "quantity": 3
}
```

```json
{
  "item_type": "product",
  "item_id": 1,
  "quantity": 3,
  "currency": "COP",
  "customer_unit_price": "18000.00",
  "customer_subtotal": "54000.00",
  "preview_total": "54000.00",
  "pricing_rule": "temporary_product_base_price_v1",
  "provider_quote_reference": "local-quote-product-1"
}
```

### Pricing Rejection

```json
{
  "detail": {
    "code": "kit_pricing_deferred",
    "message": "Kit pricing preview is deferred until a documented kit pricing method exists."
  }
}
```

## Payment Initialization

```http
POST /api/v1/payments
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "order_id": 1
}
```

```json
{
  "data": {
    "payment_id": 1,
    "order_id": 1,
    "payment_status": "initiated",
    "amount": "54000.00",
    "currency": "COP"
  }
}
```

The request must not include amount, currency, ownership, status, provider
reference, card data, or payment confirmation claims. The backend derives those
values from the authenticated draft Order and its immutable OrderItem
snapshots.

## Authentication Error

```json
{
  "detail": "Invalid authentication credentials"
}
```
