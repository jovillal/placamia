# Bruno API Collection

The repository includes a demo-ready Bruno collection at:

```text
bruno/placamia-api
```

Use it for local manual API checks and demos alongside FastAPI's generated
Swagger UI at `http://localhost:8000/docs`.

The Bruno collection is not currently a complete mirror of every implemented
API endpoint. FastAPI `/docs` and `docs/api/endpoint-structure.md` remain the
endpoint inventory source of truth.

## Open In Bruno

1. Start the local backend:

```bash
make dev
```

2. Open Bruno.
3. Choose **Open Collection**.
4. Select the `bruno/placamia-api` directory.
5. Select the `Local` environment.

The `Local` environment points at:

```text
http://localhost:8000
```

## Included Requests

- `Health / Health Check`
- `Catalog / List Categories`
- `Catalog / List Products`
- `Catalog / Get Product`
- `Catalog / List Kits`
- `Catalog / Get Kit`
- `Pricing / Quote Product`
- `Pricing / Quote Kit`
- `Pricing / Quote Design`
- `Auth / Current User`
- `Orders / List Orders`
- `Payments / Initialize Payment`

The catalog and Product/Kit pricing requests are public. `Pricing / Quote
Design` loads an owner-scoped persisted Design and uses the `access_token`
environment variable. It returns `401` until a valid local bearer token is
provided. `Auth / Current User` and `Payments / Initialize Payment` also use
`access_token`. `Orders / List Orders` also uses `order_page` and
`order_page_size`; payment initialization expects `payment_order_id` to point
at an eligible authenticated draft order.

## Local Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `base_url` | `http://localhost:8000` | Local API origin. |
| `api_prefix` | `/api/v1` | Versioned API prefix. |
| `product_id` | `1` | Product id used by `Catalog / Get Product`. |
| `kit_id` | `1` | Kit id used by `Catalog / Get Kit` and `Pricing / Quote Kit`. |
| `design_id` | `1` | Owned persisted Design id used by `Pricing / Quote Design`. |
| `pricing_quantity` | `1` | Quantity used by all pricing preview requests. |
| `payment_order_id` | `1` | Draft order id used by `Payments / Initialize Payment`. |
| `order_page` | `1` | One-based page used by `Orders / List Orders`. |
| `order_page_size` | `20` | Bounded page size used by `Orders / List Orders`. |
| `access_token` | empty | Optional bearer token for authenticated requests. |
