# Bruno API Collection

The repository includes a demo-ready Bruno collection at:

```text
bruno/placamia-api
```

Use it for local manual API checks and demos alongside FastAPI's generated
Swagger UI at `http://localhost:8000/docs`.

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
- `Auth / Current User`

The catalog requests are public. `Auth / Current User` uses the `access_token`
environment variable and returns `401` until a valid local bearer token is
provided.

## Local Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `base_url` | `http://localhost:8000` | Local API origin. |
| `api_prefix` | `/api/v1` | Versioned API prefix. |
| `product_id` | `1` | Product id used by `Catalog / Get Product`. |
| `access_token` | empty | Optional bearer token for authenticated requests. |
