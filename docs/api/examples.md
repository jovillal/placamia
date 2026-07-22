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

### Catalog Kit Detail

```http
GET /api/v1/catalog/kits/1
```

```json
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
```

The detail response uses the same public Kit projection as its list entry.
Unknown, inactive, empty, and all-inactive Kits return `404 Kit not found`.
The endpoint accepts no query parameters; submitted parameters return HTTP 422
`unsupported_query_parameter`. Kit pricing remains available only through the
pricing preview endpoint.

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

### Fixed-Content Kit Pricing Preview

```json
{
  "item_type": "kit",
  "item_id": 10,
  "quantity": 3,
  "options": {}
}
```

```json
{
  "item_type": "kit",
  "item_id": 10,
  "quantity": 3,
  "currency": "COP",
  "customer_unit_price": "50000.00",
  "customer_subtotal": "150000.00",
  "preview_total": "150000.00",
  "pricing_rule": "temporary_kit_contents_base_price_v1",
  "provider_quote_reference": "local-quote-kit-10",
  "lines": [
    {
      "product_id": 1,
      "product_name": "Exit route sign",
      "quantity_per_kit": 2,
      "total_quantity": 6,
      "customer_unit_price": "20000.00",
      "customer_subtotal": "120000.00"
    },
    {
      "product_id": 2,
      "product_name": "Assembly point sign",
      "quantity_per_kit": 1,
      "total_quantity": 3,
      "customer_unit_price": "10000.00",
      "customer_subtotal": "30000.00"
    }
  ]
}
```

### Persisted Design Pricing Preview

```http
POST /api/v1/pricing/quotes
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "item_type": "design",
  "item_id": 7,
  "quantity": 2
}
```

```json
{
  "item_type": "design",
  "item_id": 7,
  "quantity": 2,
  "currency": "COP",
  "customer_unit_price": "20000.00",
  "customer_subtotal": "40000.00",
  "preview_total": "40000.00",
  "pricing_rule": "temporary_design_product_base_price_v1",
  "provider_quote_reference": "local-quote-design-7"
}
```

The backend loads the owned Design, revalidates its persisted customization,
and derives the Product base price through the Design's Template. Design quote
requests cannot submit customization, Product, price, provider, or ownership
fields.

Any extra Design request field returns HTTP 400:

```json
{
  "detail": {
    "code": "frontend_pricing_claim_not_allowed",
    "message": "Extra frontend claims are not accepted for Design pricing."
  }
}
```

Malformed, unsupported, or no-longer-valid persisted customization is hidden
behind one aggregate HTTP 400 response:

```json
{
  "detail": {
    "code": "design_configuration_unavailable",
    "message": "Design configuration is unavailable."
  }
}
```

## Customer Order List

```http
GET /api/v1/orders?page=1&page_size=20
Authorization: Bearer <access_token>
```

```json
{
  "data": [
    {
      "id": 42,
      "status": "confirmed",
      "currency": "COP",
      "total_amount": "85000.00",
      "created_at": "2026-07-21T12:00:00Z",
      "updated_at": "2026-07-21T12:05:00Z"
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

The backend derives ownership from the bearer token and applies it to both the
list and count queries. Results use persisted Order totals and currency, order
by `created_at DESC, id DESC`, and expose no OrderItem, Payment, customer,
provider, policy, cancellation-provenance, or internal fields. Only `page` and
`page_size` are supported; other query parameters return HTTP 422
`unsupported_query_parameter`.

## Customer Order Detail

```http
GET /api/v1/orders/42
Authorization: Bearer <access_token>
```

```json
{
  "id": 42,
  "status": "confirmed",
  "currency": "COP",
  "subtotal_amount": "85000.00",
  "discount_amount": "0.00",
  "tax_amount": "0.00",
  "total_amount": "85000.00",
  "payment_verified_at": "2026-07-21T12:05:00Z",
  "provider_handoff_sent_at": null,
  "created_at": "2026-07-21T12:00:00Z",
  "updated_at": "2026-07-21T12:05:00Z",
  "items": [
    {
      "item_type": "product",
      "display_name": "Emergency exit sign",
      "customer_safe_description": "Standard exit signage.",
      "selected_options": {},
      "quantity": 2,
      "unit_price_amount": "42500.00",
      "line_subtotal_amount": "85000.00",
      "line_discount_amount": "0.00",
      "line_tax_amount": "0.00",
      "line_total_amount": "85000.00",
      "currency": "COP"
    }
  ]
}
```

The backend scopes the Order lookup by both route id and authenticated owner.
Unknown and cross-customer ids return the same `404 Order not found` response.
All values come from persisted Order and OrderItem snapshots; mutable catalog,
pricing, Payment, and provider relationships are not used for projection.
Every query parameter is rejected with HTTP 422
`unsupported_query_parameter` after successful authentication.

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
