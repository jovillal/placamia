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

## Temporary Product Pricing Preview

Issue #27 defines the first customer-facing pricing preview service for Path A
products only. Until validation fills `docs/validation/pricing-model.md`, the
temporary product preview rule is:

- customer unit price: backend `Product.base_price`
- customer subtotal: temporary unit price multiplied by quantity
- customer total: subtotal for this slice only

The #27 preview does not model margin, tax, fee, discount, or checkout
finalization rules. Provider cost/capability input is required for backend
eligibility and traceability, but provider cost is not exposed as a
customer-facing amount.

## Temporary Fixed-Content Kit Pricing Preview

Issue #183 extends the existing public quote endpoint to fixed-content Kits.
Until validation fills `docs/validation/pricing-model.md`, the temporary rule
`temporary_kit_contents_base_price_v1` uses only persisted backend catalog data:

- each line's quantity per Kit is `KitItem.quantity`
- each line's effective quantity is `KitItem.quantity` multiplied by the
  requested Kit quantity
- each line's customer unit price is the related `Product.base_price`
- each line's subtotal is customer unit price multiplied by effective quantity
- the Kit customer unit price is the sum of each Product base price multiplied
  by its quantity per Kit
- the Kit subtotal and preview total are the sum of line subtotals

The fixed Kit response is a direct resource with this exact public shape:

```json
{
  "item_type": "kit",
  "item_id": 10,
  "quantity": 3,
  "currency": "COP",
  "customer_unit_price": "50.00",
  "customer_subtotal": "150.00",
  "preview_total": "150.00",
  "pricing_rule": "temporary_kit_contents_base_price_v1",
  "provider_quote_reference": "local-quote-kit-10",
  "lines": [
    {
      "product_id": 1,
      "product_name": "Exit route sign",
      "quantity_per_kit": 2,
      "total_quantity": 6,
      "customer_unit_price": "20.00",
      "customer_subtotal": "120.00"
    },
    {
      "product_id": 2,
      "product_name": "Assembly point sign",
      "quantity_per_kit": 1,
      "total_quantity": 3,
      "customer_unit_price": "10.00",
      "customer_subtotal": "30.00"
    }
  ]
}
```

Lines are returned in persisted `KitItem.id` order. Distinct KitItem rows remain
distinct even when they reference the same Product. The temporary rule applies
no tax, fee, margin, discount, or provider-cost arithmetic.

Kit quote requests use the requested Kit quantity for Kit-level provider checks
and the effective Product quantity for each required-content provider check.
Both the requested Kit quantity and every effective Product quantity must be at
most 100. Provider cost/capability input remains required for eligibility and
traceability, but no provider cost or Product-level provider reference is
exposed in the public response.

The Kit quote contract accepts no editable contents or options and rejects all
extra frontend claims. Inactive Kits, empty Kits, invalid persisted quantities,
unavailable required contents, manual-quote-only states, and missing provider
cost input are rejected without persistence or provider handoff side effects.
Inactive required contents use the aggregate customer-safe reason
`kit_contents_unavailable`.

This issue implements pricing preview only. Kit checkout, orders, payment, and
provider handoff remain outside #183.

## Temporary Persisted Design Pricing Preview

Issue #184 extends the same quote endpoint to authenticated customer-owned
Designs. Every Template has one required backend-owned Product relationship,
and the pricing service derives the sellable anchor through
`Design -> Template -> Product`. The client cannot submit or override that
Product relationship.

The temporary `temporary_design_product_base_price_v1` rule is:

- customer unit price: related active backend `Product.base_price`
- customer subtotal: customer unit price multiplied by requested quantity
- preview total: subtotal for this slice only
- persisted customization: revalidated and passed to Design provider checks,
  but does not change the temporary customer amount

The authenticated request accepts exactly:

```json
{
  "item_type": "design",
  "item_id": 7,
  "quantity": 2
}
```

Successful pricing returns a direct discriminated resource:

```json
{
  "item_type": "design",
  "item_id": 7,
  "quantity": 2,
  "currency": "COP",
  "customer_unit_price": "20.00",
  "customer_subtotal": "40.00",
  "preview_total": "40.00",
  "pricing_rule": "temporary_design_product_base_price_v1",
  "provider_quote_reference": "local-quote-design-7"
}
```

Unknown and cross-customer Designs both return HTTP 404 `design_not_found`
without revealing ownership. Inactive Templates return HTTP 400
`inactive_template`, inactive Products return HTTP 400 `inactive`, and
malformed, unsupported, or no-longer-valid persisted customization returns
HTTP 400 `design_configuration_unavailable` with the aggregate message
`Design configuration is unavailable.` Provider availability, capability,
eligibility, and missing-cost rejection codes remain backend-derived.

Design quote requests forbid `options` and every extra customization, Product,
price, provider, ownership, role, or arbitrary field. Every extra field returns
HTTP 400 `frontend_pricing_claim_not_allowed` with the Design-specific message
`Extra frontend claims are not accepted for Design pricing.` Product and Kit
quote requests remain public; only Design pricing requires authentication, and
invalid supplied credentials never downgrade a Design request to anonymous
access. Provider cost, assignment, availability, eligibility, lead time,
persisted customization, Product mapping, and ownership are not returned. The
opaque provider quote reference remains customer-visible for parity with
Product and Kit previews.

This rule applies no customization adjustment, margin, tax, fee, or discount.
Those calculations remain deferred until validation documents exact rules.
Design checkout, orders, payment, and provider handoff remain outside #184.

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
