# MVP Scope

## Product Decision

The MVP follows Path A: direct checkout for products and kits that are fully
parametrizable, compatible with provider adapter boundary responses, and
priceable by backend-owned rules.

Partner-specific validation findings may name the provider that supplied them,
but the MVP should model providers generically so future manufacturing
providers can be added without changing customer checkout behavior.

Availability, provider cost/capability inputs, direct-checkout eligibility,
lead time, paid-order handoff, handoff status, and provider
acceptance/rejection must go through the provider adapter boundary.

## Included
- user can browse the product and kit catalog
- user can browse template catalog
- user can create a design from a template
- user can customize template fields through rules-based options
- user can request backend pricing for direct-checkout items
- user can complete checkout
- user can place an order
- user can track order status

## Excluded for now
- AI-assisted variation generation
- basic credit consumption model
- gamified credit systems
- advanced analytics
- multi-tenant admin tools
- manufacturer optimization features
- complex discount engines
- RFQ/provider-confirmed checkout before payment
- manual-quote products in direct checkout
- exact provider inventory reservation
- automated provider payout, invoicing, or SLA enforcement

## Post-MVP Notes

AI-assisted features and credit systems may be reconsidered after the MVP, but
they are not part of the current catalog, rules-based customization, pricing,
checkout, or order tracking scope.

RFQ flows and manual provider-confirmed pricing may be reconsidered after the
direct-checkout MVP proves demand. Until then, products that require manual
quoting or provider confirmation must not be sold through checkout.
