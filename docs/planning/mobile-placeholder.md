# Mobile Placeholder

## Goal

Prepare a minimal mobile application placeholder for future MVP user flows
without pulling mobile implementation into the backend-first milestones.

The placeholder should help validate navigation and screen structure later
while keeping current backend planning as the primary implementation focus.

## Scope

- Initial MVP screen map
- Expo placeholder scaffold
- Mobile project structure under `apps/mobile`

## Path A MVP Screen Map

This screen map is the customer-facing mobile contract map for the Path A MVP.
It is not a visual design specification and does not create backend API
behavior. Mobile implementation must treat backend-derived catalog eligibility,
pricing, order state, and payment verification as authoritative.

Dependency status labels:

- `Implemented`: present in `docs/api/endpoint-structure.md` and current
  backend planning docs.
- `Documented-but-pending`: required by planning docs, but no stable customer
  endpoint or response contract exists yet.
- `Intentionally deferred`: outside the Path A MVP or explicitly postponed by
  planning docs.

### 1. Authentication Entry

Purpose:

- Let a returning customer enter the app with an authenticated context when a
  token/session already exists.
- Keep unauthenticated users on public catalog browsing until a protected
  action requires authentication.

Key actions:

- Open app.
- Check authenticated customer context.
- Continue to catalog, sign in, or stay in public browse mode.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/auth/me` | Implemented | Returns authenticated user context for protected flows. |
| Customer token acquisition/sign-in endpoint | Documented-but-pending | The endpoint inventory only lists `GET /auth/me`; #37 may use static/mock authenticated state for navigation only, with no embedded credential, token, session, or backend-auth bypass. |

### 2. Catalog Home And Category Browse

Purpose:

- Let customers browse public catalog groupings without authentication.
- Keep catalog navigation read-only.

Key actions:

- View categories.
- Select a category.
- Navigate to product or kit browsing.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/catalog/categories` | Implemented | Public category collection. |
| Public catalog eligibility rules | Implemented | Eligibility remains backend-derived; the app must not supply provider, availability, lead time, price, or direct-checkout claims. |

### 3. Product List

Purpose:

- Show active products with backend-derived direct-checkout signals.
- Let customers filter by category and page through the public catalog.

Key actions:

- Browse products.
- Filter by `category_id`.
- Page using `page` and `page_size`.
- Open product detail.
- Treat non-eligible products as not directly purchasable.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/catalog/products` | Implemented | Supports `category_id`, `page`, and `page_size` only. |
| Product eligibility fields | Implemented | Uses `availability_state`, `direct_checkout_eligible`, `eligibility_reason`, `production_lead_time_days`, and `dispatch_lead_time_days`. |
| Client-side provider or price filters | Intentionally deferred | The public contract rejects arbitrary provider, availability, price, lead-time, eligibility, and sorting controls. |

### 4. Product Detail

Purpose:

- Show customer-safe product information and backend-derived purchasability.
- Provide an entry point to supported customization or pricing preview.

Key actions:

- View product metadata.
- Review direct-checkout eligibility and lead time.
- Continue to supported customization/design input when available.
- Request pricing preview for eligible product configurations.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/catalog/products/{product_id}` | Implemented | Public product detail for active products. |
| Product direct-checkout eligibility | Implemented | Backend-owned and output-only. |

### 5. Kit List

Purpose:

- Show active public kits with customer-safe active product summaries.
- Preserve kit-level backend-derived eligibility.

Key actions:

- Browse kits.
- Inspect kit contents.
- See whether the kit is directly purchasable.
- Continue to kit detail.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/catalog/kits` | Implemented | Returns visible active kits and customer-safe product summaries for contents. |
| Kit visibility and eligibility contract | Implemented | Kits with zero active required contents are hidden; active unavailable/manual-quote/non-priceable contents remain listed and make the kit not directly purchasable. |
| Kit provider/internal fields | Intentionally deferred | Provider cost, assignment, raw provider payloads, and internal eligibility inputs must not be exposed. |

### 6. Kit Detail

Purpose:

- Let customers inspect one kit before pricing or checkout.
- Avoid forcing the mobile app to infer kit detail from list data forever.

Key actions:

- View kit metadata.
- Review customer-safe content summaries.
- Review kit-level direct-checkout eligibility and lead time.
- Continue to pricing only when eligible.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/catalog/kits/{kit_id}` | Implemented | Public direct `KitRead` detail with the same visibility, active-content projection, and eligibility behavior as the Kit list. |
| Kit pricing interaction | Implemented | Fixed-content Kits use backend KitItem quantities and Product base prices for temporary quote previews. |

### 7. Template Selection And Rules-Based Design Input

Purpose:

- Support the MVP path where a customer creates a rules-based customized
  design from a backend Template.
- Avoid AI, AR, 3D rendering, file review, and unsupported generation flows.

Key actions:

- Browse/select an active Template.
- Fill backend-defined TemplateFields.
- Submit customization values.
- Receive a persisted Design only after backend validation succeeds.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/templates` | Implemented | Public active Template summaries with deterministic ordering. |
| `GET /api/v1/templates/{template_id}` | Implemented | Public active Template detail with active backend-owned TemplateFields. |
| `POST /api/v1/designs` | Implemented | Authenticated creation persists only backend-validated customization for the current customer. |
| `GET /api/v1/designs/{design_id}` | Implemented | Authenticated owner-only retrieval with customer-safe not-found behavior. |
| AI/AR/3D/file-based design generation | Intentionally deferred | Out of MVP scope. |

### 8. Pricing Preview

Purpose:

- Show backend-calculated customer pricing before checkout.
- Prevent the mobile app from owning totals, provider cost, or eligibility.

Key actions:

- Submit supported Product, fixed-content Kit, or owned persisted Design pricing
  inputs.
- Display backend-calculated amount and currency.
- Reject or block checkout for inactive, unavailable, manual-quote-only,
  non-priceable, or invalid configurations.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `POST /api/v1/pricing/quotes` | Implemented | Public Product/Kit and authenticated owner-scoped Design pricing preview endpoint. |
| Product pricing preview | Implemented | Temporary Path A product rule uses backend `Product.base_price` and quantity. |
| Kit pricing preview | Implemented | Temporary fixed-content rule uses backend KitItems, Product base prices, and effective quantities. |
| Persisted Design pricing preview | Implemented | Owner-scoped persisted customization is revalidated and priced from the Template's related Product base price. |
| Frontend-supplied totals/provider cost | Intentionally deferred | Must be ignored or rejected; never authoritative. |

### 9. Checkout Review

Purpose:

- Let an authenticated customer review backend-derived checkout state before
  order creation and payment.
- Show cancellation/refund terms before payment.

Key actions:

- Review item snapshots, quantities, amount, currency, and lead-time signals
  returned or derived by backend contracts.
- Review cancellation/refund terms.
- Confirm checkout only after terms are acknowledged.
- Create a draft order from backend-validated state.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `POST /api/v1/orders` | Implemented | Authenticated draft order creation from backend-validated checkout state. |
| Cancellation/refund terms policy acknowledgement | Implemented | Orders persist a terms policy identifier/version before payment. |
| Customer-visible terms content surface | Documented-but-pending | #37 may display clearly labeled sample terms copy for navigation only until a stable terms-content endpoint exists; placeholder copy must not be presented as a production legal policy. |
| Frontend ownership, price, or provider claims | Intentionally deferred | Checkout must derive owner from auth and totals from backend pricing/order logic. |

### 10. Payment Initiation

Purpose:

- Initialize or reuse a backend-owned payment attempt for the authenticated
  customer's eligible draft order.
- Avoid card storage and provider secret exposure.

Key actions:

- Start payment for a draft order.
- Display initialized, pending, or retry-safe active payment attempt state.
- Keep order unconfirmed until backend verifies provider payment confirmation.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `POST /api/v1/payments` | Implemented | Accepts only `order_id`; returns payment id, order id, status, amount, and currency. |
| Wompi Web Checkout redirect handoff | Provider-selected; implementation pending | ADR 0004 defines a provider-neutral redirect response; #186 must implement it before mobile wiring. |
| Card data collection/storage in PlacamIA backend | Intentionally deferred | Backend must not store card data. |

### 11. Payment Result States

Purpose:

- Represent payment outcomes without trusting frontend return pages as payment
  confirmation.
- Keep retry behavior compatible with backend payment lifecycle.

Customer-visible states:

| State | Mobile meaning | Backend source |
| --- | --- | --- |
| `initiated` | Backend created or reused an active attempt. | `POST /api/v1/payments` |
| `pending` | One or more provider transactions are still processing. | Persisted aggregate state from a trusted provider webhook or reconciliation. |
| `requires_action` | Customer action or another retry is possible. | Persisted aggregate state; one declined Wompi transaction does not necessarily end the Payment. |
| `verified` / success | At least one trusted matching transaction was approved; order may become confirmed. | Provider-specific webhook or backend reconciliation plus order status. |
| `failed` | The Payment aggregate can no longer succeed and the order must not be confirmed. | Persisted aggregate state from trusted provider observations. |
| `cancelled` | The Payment aggregate was cancelled and the order must not be confirmed. | Persisted aggregate state from trusted provider observations. |
| `expired` | The checkout-start window ended; stop polling and offer the documented retry path. A later trusted provider settlement may still update backend state. | Persisted aggregate state from trusted provider observations and backend time rules. |

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `POST /api/v1/payments/webhook` | Implemented | Backend/provider boundary only; not called by the mobile app. |
| `POST /api/v1/payments/webhooks/wompi` | Provider-selected; implementation pending | Provider-specific route authenticates Wompi events before common lifecycle processing; never called by mobile. |
| Customer payment-status polling endpoint | Documented-but-pending | #187 must return persisted canonical aggregate state. Mobile must not query Wompi directly or treat the browser return as confirmation. |
| Frontend payment success claim | Intentionally deferred | Never marks payment verified or order confirmed. |

### 12. Order List

Purpose:

- Let authenticated customers find previous or active orders.

Key actions:

- View customer-owned order summaries.
- Open an order detail/tracking screen.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/orders` | Implemented | Authenticated owner-scoped summaries with deterministic pagination and persisted totals. |
| Cross-user order visibility | Implemented | Backend list and count queries enforce ownership; mobile must not client-filter ownership. |

### 13. Order Detail And Tracking

Purpose:

- Let authenticated customers track backend-owned order lifecycle state.
- Show immutable customer-safe purchased-item snapshots.
- Show cancellation request actions only in allowed paid states.

Key actions:

- View status.
- View customer-safe tracking fields.
- Request cancellation from eligible states.
- Display cancellation request outcome.

Backend dependencies:

| Dependency | Status | Notes |
| --- | --- | --- |
| `GET /api/v1/orders/{order_id}` | Implemented | Authenticated owner detail using persisted Order and immutable OrderItem snapshots only. |
| `GET /api/v1/orders/{order_id}/status` | Implemented | Authenticated owner status retrieval. |
| `POST /api/v1/orders/{order_id}/cancellation-request` | Implemented | Owning customer can request cancellation from `confirmed`, `accepted`, or `in_production`. |
| Admin/provider mutation endpoints | Implemented, not mobile-facing | Acceptance, production, shipment, delivery, and cancellation review endpoints are admin/provider scope, not customer UI actions. |

Customer-visible status terminology must match the canonical lifecycle:

- `draft`
- `confirmed`
- `sent_to_provider`
- `accepted`
- `in_production`
- `ready_for_pickup`
- `shipped`
- `delivered`
- `cancellation_requested`
- `cancelled`

The mobile app must not invent provider/admin-only statuses or expose provider
accept/reject controls to customers.

## Deferred Customer UX

These flows are intentionally outside this screen map:

- RFQ/manual quote UX.
- Provider, operator, or admin UI.
- Refund processing UI and payout/invoice UI.
- Exact inventory reservation.
- Unsupported design capabilities such as AI, AR, 3D rendering, file review,
  image generation, collaborative design, or advanced analytics.

## Minimum API Contract Gaps Before Real Backend Wiring

#37 can begin as a deliberately thin Expo placeholder with static/mock data and
navigation placeholders if it does not pretend these gaps are implemented.

Backend gaps to resolve before connecting each screen to real behavior:

- #179: customer sign-in/token acquisition flow beyond `GET /auth/me`.
- #185: versioned customer-visible cancellation/refund terms content source.
- #186: real-provider payment initialization handoff response. The current
  provider-neutral `POST /api/v1/payments` attempt initialization is already
  implemented and must not be presented as a real provider session. ADR 0004
  selects Wompi Web Checkout and defines the provider-neutral redirect shape.
- #187: customer payment-status polling or documented order/payment result
  reconciliation for mobile state refresh. The documented read source is
  persisted Payment aggregate state, not frontend return parameters.

## #37 Implementation Guardrails

The Expo placeholder must stay non-authoritative and non-production-facing:

- No real authentication flow, embedded credentials, bearer tokens, persisted
  sessions, or backend-auth bypass.
- No production API base URL or production customer data.
- No persisted customer, payment, order, or provider data.
- No checkout submission against live backend state.
- No payment provider SDK, provider payment session, card collection, or raw
  provider payload handling.
- No direct mobile calls to payment webhook, provider, operator, or admin
  endpoints.
- No static legal copy presented as production cancellation/refund policy.
- No real-time payment confirmation claims without a documented customer
  payment-status refresh contract.

## Related Docs

- `docs/product/user-flows.md`
- `docs/product/mvp-scope.md`
- `docs/flows/main-flow.md`
- `docs/flows/catalog-flow.md`
- `docs/flows/checkout-flow.md`
- `docs/planning/catalog.md`
- `docs/planning/kits.md`
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`

## Child Issues

Completed:

- #36 Define initial screen map for MVP flow
- #37 Scaffold Expo placeholder app

Backend contract backlog:

- #179 and #185 through #187, mapped individually in
  `Minimum API Contract Gaps Before Real Backend Wiring`.

## Constraints

- Mobile backend wiring follows the `Current MVP` milestone and the dependency
  status of each screen; it is not governed by the retired phase labels.
- Do not implement backend behavior in mobile placeholder issues.
- Do not introduce AI, AR, 3D rendering, or gamified credit systems.
- Keep the placeholder aligned with MVP flow: catalog, templates/designs,
  pricing, checkout, orders, payments, and order tracking.

## Done When

- Initial MVP screen map is documented.
- Screen dependencies are labeled as implemented, documented-but-pending, or
  intentionally deferred.
- #37 can start with placeholder/static/mock data without redefining backend
  contracts.
- Placeholder mobile app scaffold exists.
- Mobile structure does not redefine backend API contracts.
- Future mobile work can reference backend API planning docs.
