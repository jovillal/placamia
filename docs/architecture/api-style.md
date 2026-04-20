# API Style Guide

## Base Path

/api/v1

---

## Naming

- plural resources
- REST-like structure

Examples:

GET /api/v1/products  
GET /api/v1/products/{id}  
POST /api/v1/orders  

---

## Responses

### Success

```json
{
  "data": {}
}
```
### Error
```json
{
  "error": "message"
}
```

### Status Codes
 - 200 OK
 - 201 Created
 - 400 Bad Request
 - 404 Not Found
 - 500 Internal Error

## Request Rules
 - Use JSON bodies for POST/PUT
 - Validate inputs using Pydantic schemas
 - Do not accept raw/unvalidated input

## Pagination (Future)

Use:

 - limit
 - offset

## Versioning

All endpoints must be under:

  /api/v1

Future versions will use:

  /api/v2

## Endpoint Design Rules

 - Keep endpoints simple
 - Do not overload endpoints with multiple responsibilities
 - Business logic must not be inside route handlers
 - Use services layer for logic

## Error Handling
 - Return meaningful error messages
 - Do not expose internal exceptions
 - Use consistent error structure

## Performance

 - Avoid unnecessary DB queries
 - Prefer explicit queries over ORM magic when needed