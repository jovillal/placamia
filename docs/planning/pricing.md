# Pricing

## Goal

Provide accurate, backend-calculated pricing for designs and kits.

Pricing must be deterministic, secure, and independent of any
frontend-provided totals.

This is a critical system that directly impacts revenue and security.

The MVP follows Path A: direct checkout is available only for products, kits,
and design configurations that are fully parametrizable and can be priced by
backend-owned rules without manual provider quoting. Provider cost,
availability, eligibility, and lead time inputs come through the provider
adapter boundary; they are inputs to backend decisions, not frontend-supplied
truth.

## Core Principles

- Backend is the single source of truth for pricing
- Provider adapter boundary is the source for provider cost inputs,
  availability, direct-checkout eligibility, and lead time signals
- Frontend-provided prices are ignored
- Pricing must be recalculated on every request
- Invalid configurations must be rejected
- Provider adapter outputs may inform backend pricing and checkout eligibility,
  but the backend still calculates the final customer-facing price
- Manual quotes and provider-confirmed pricing are out of scope for direct
  checkout MVP items

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
   - product or kit is eligible for direct checkout
   - provider adapter availability and eligibility allow sale
   - provider adapter lead time response is compatible with checkout display
4. Backend calculates:
   - provider cost inputs from the provider adapter boundary
   - base price
   - adjustments (material, size)
   - quantity multiplier
   - discounts (if applicable)
5. Backend returns calculated pricing

## Scope

- Pricing rule definition
- Pricing calculation service
- Pricing preview endpoint
- Direct-checkout eligibility validation for pricing requests
- Provider cost input handling through the provider adapter boundary

## Path A Pricing Contract

Issue #26 defines the first backend service contract for direct-checkout
pricing. The initial contract is intentionally service-level only; public quote
and checkout endpoints are handled by later issues.

Supported contract targets:

- product pricing contract validation for backend `Product` records
- kit pricing contract validation for backend-owned `KitItem` contents
- design pricing boundary with explicit rejection until design pricing rules
  are defined

Issue #26 does not define customer price composition, kit aggregation formulas,
margin, tax, fee, discount, subtotal, total, or checkout amount behavior. Those
belong to later pricing implementation issues.

Backend pricing requests must:

- use backend-loaded catalog models, not request-provided catalog contents
- validate quantity before calculation
- reject unsupported material, size, finish, template, or design options
- reject frontend-supplied totals, subtotals, discounts, provider costs,
  availability, eligibility, provider assignment, lead time, or final amounts
- use provider adapter availability, direct-checkout eligibility, and provider
  cost/capability inputs as backend-only inputs

Initial quantity limits:

- minimum quantity: 1
- maximum quantity: 100

Products and kits must be rejected before price calculation when they are:

- inactive
- unavailable through the provider adapter boundary
- manual-quote-only
- outsourced or not safe for MVP direct checkout
- missing provider cost/capability input
- not compatible with backend-owned pricing configuration rules

Provider cost inputs are kept as traceable backend inputs. They are not
customer-facing prices and must never be accepted from frontend payloads.

## Related Validation Docs

- `docs/planning/provider.md`
- `docs/planning/provider-adapter-contract.md`
- `docs/validation/pricing-model.md`
- `docs/validation/product-classification.md`
- `docs/validation/availability-model.md`

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
- Provider cost inputs, availability, direct-checkout eligibility, and lead
  time must come through the backend provider adapter boundary, starting with a
  local/mock adapter for MVP backend development
- Pricing must reject any product, kit, design, material, size, finish,
  quantity, or customization value that cannot be deterministically priced
- Products or configurations that require manual provider confirmation must not
  return a checkout-ready price in MVP
- Partner validation may update adapter fixtures, seed data, and future
  real-provider mappings later, but pricing implementation must not wait for a
  real-provider integration

## Security Considerations

- Ignore any frontend-provided price, subtotal, or total
- Ignore or reject frontend-supplied provider cost, provider assignment,
  availability, direct-checkout eligibility, lead time, or capability claims
- Validate all input fields
- Reject invalid or inconsistent configurations
- Prevent quantity abuse
- Reject stale, unavailable, inactive, or manual-quote-only catalog items

## Testing Requirements

Pricing must include explicit tests for:

- valid pricing calculation
- invalid product options rejected
- inactive products rejected
- unavailable or manual-quote-only products rejected
- frontend price ignored
- frontend provider cost, availability, eligibility, or lead time ignored or
  rejected
- edge cases for quantity and configuration

## Done When

- Pricing endpoint returns correct values
- Invalid inputs are rejected
- Pricing is consistent across repeated calls
- Pricing rejects items that are not eligible for direct checkout
- Tests cover all critical scenarios
