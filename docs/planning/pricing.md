# Pricing

## Goal

Provide accurate, backend-calculated pricing for designs and kits.

Pricing must be deterministic, secure, and independent of any
frontend-provided totals.

This is a critical system that directly impacts revenue and security.

## Core Principles

- Backend is the single source of truth for pricing
- Frontend-provided prices are ignored
- Pricing must be recalculated on every request
- Invalid configurations must be rejected

(See AGENTS.md and Testing Architecture)

## Flow

1. User submits a pricing request
2. Backend receives:
   - design id OR configuration (template + options)
   - quantity
3. Backend validates:
   - template exists
   - options are valid
   - product is active
4. Backend calculates:
   - base price
   - adjustments (material, size)
   - quantity multiplier
   - discounts (if applicable)
5. Backend returns calculated pricing

## Scope

- Pricing rule definition
- Pricing calculation service
- Pricing preview endpoint

## Related Endpoints

- POST /api/v1/pricing/quotes

(See docs/api/endpoint-structure.md)

## Child Issues

- #26 Define pricing rule model
- #27 Implement pricing preview logic
- #28 Create POST pricing preview endpoint with tests

## Related Security Milestone

- #51 Add server-side quote and checkout pricing test foundation

## Future Issues

- Future issue required: add pricing validation tests for edge cases
- Future issue required: add rejection logic for invalid configurations
- Future issue required: add logging for pricing mismatches without sensitive
  data

## Constraints

- Pricing must never rely on frontend values
- Pricing must be reproducible from stored data
- Pricing must handle:
  - products
  - kits
  - designs

## Security Considerations

- Ignore any frontend-provided price, subtotal, or total
- Validate all input fields
- Reject invalid or inconsistent configurations
- Prevent quantity abuse

## Testing Requirements

Pricing must include explicit tests for:

- valid pricing calculation
- invalid product options rejected
- inactive products rejected
- frontend price ignored
- edge cases for quantity and configuration

## Done When

- Pricing endpoint returns correct values
- Invalid inputs are rejected
- Pricing is consistent across repeated calls
- Tests cover all critical scenarios
