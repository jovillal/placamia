# Payments

## Goal

Verify customer payment before an order can move into confirmed fulfillment.

Payments are a security-critical boundary. The backend must never fulfill an
order based only on frontend confirmation.

## Core Principles

- Do not store card data.
- Use a payment provider for payment processing.
- Store only the provider identity, safe payment/transaction/event references,
  statuses, order id, amount, currency, and timestamps needed for lifecycle,
  reconciliation, replay protection, and support.
- Verify payment-provider confirmation before marking an order as paid.
- Reject invalid or missing webhook signatures.
- Replayed payment events must not reapply state changes.
- Provider handoff and provider acceptance or rejection happen through the
  provider adapter boundary after verified payment and must not be treated as
  payment confirmation.

## Flow

1. User starts checkout
2. Backend creates or prepares payment request
3. User completes payment through provider flow
4. Provider sends confirmation/webhook
5. Backend verifies signature and payload
6. Backend updates Payment state
7. Backend moves Order from `draft` to `confirmed`
8. Backend attempts provider adapter handoff for the confirmed paid order
9. Provider adapter records provider acceptance or rejection after handoff

## Scope

- Payment model
- Payment status lifecycle
- Payment provider reference
- Payment provider selection and merchant reference
- Provider transaction and event history
- Payment webhook/confirmation endpoint
- Signature validation
- Payment-to-order transition

## Payment Status Lifecycle

Path A payment status transitions are deterministic and backend-owned. This
section defines lifecycle/domain validation only; it does not implement payment
provider SDK calls, payment initialization, webhook endpoints, signature
verification, or database persistence by itself.

Canonical payment statuses:

- `initiated`: backend-created payment attempt before the payment provider has
  reported a durable outcome.
- `pending`: payment provider has accepted the attempt and has not reported a
  final outcome.
- `requires_action`: payment provider requires customer-side action before a
  final outcome is available.
- `verified`: payment provider confirmation has been verified by the backend.
- `failed`: the Payment aggregate can no longer produce a successful provider
  transaction and failed.
- `cancelled`: the Payment aggregate was explicitly cancelled and can no longer
  produce a successful provider transaction.
- `expired`: the Payment aggregate's checkout-start window ended without an
  approved transaction.

Customer-terminal payment statuses:

- `verified`
- `failed`
- `cancelled`
- `expired`

`is_terminal` in the customer refresh contract means the client stops polling
or reusing that checkout. It does not let PlacamIA ignore later authenticated
financial settlement. `verified`, `failed`, and `cancelled` are irreversible in
the MVP. `expired` has the narrow trusted-provider recovery transitions below.

Allowed transitions:

- `initiated -> pending` when the payment provider reports pending processing.
- `initiated -> requires_action` when the payment provider requires customer
  action.
- `initiated|pending|requires_action -> verified` only after trusted,
  verified payment-provider confirmation.
- `pending <-> requires_action` when the payment provider changes the required
  customer/provider processing state.
- `initiated|pending|requires_action -> failed` when a trusted aggregate
  observation proves the Payment can no longer succeed.
- `initiated|pending|requires_action -> cancelled` when a trusted provider or
  backend-owned action cancels the aggregate.
- `initiated|pending|requires_action -> expired` when the checkout-start window
  ends without an approved transaction and no in-flight transaction remains.
- `expired -> pending` when an authenticated provider webhook or trusted
  reconciliation proves that a transaction started before expiration remains
  in flight.
- `expired -> verified` when an authenticated provider webhook or trusted
  reconciliation proves that a transaction started before expiration was
  approved and its identity, amount, and currency match persisted Payment.

Provider transaction statuses are observations beneath this lifecycle. One
declined or failed transaction is not itself a transition to terminal Payment
state while another retry remains possible. `checkout_expires_at` closes new
customer transaction starts; it does not invalidate a transaction already
accepted by the provider.

Invalid transitions must be rejected without mutating persisted payment or
order state. Frontend return pages, frontend payment claims, provider adapter
events, and provider acceptance/rejection must never create a `verified`
payment state.

## Payment-To-Order Transition

An Order may move from `draft` to `confirmed` only when:

1. The payment status is `verified`.
2. The payment verification source is a trusted payment-provider webhook or
   backend payment-provider reconciliation path.
3. The Order is still in `draft`.

Failed, cancelled, expired, initiated, pending, or requires-action payments
must not confirm an order. A late approved observation first moves `expired` to
`verified`; only that verified state may confirm a still-draft Order. Replayed
payment events must not duplicate state changes or side effects.

## Provider Handoff Eligibility

Provider handoff is downstream of payment verification. A paid order is eligible
for handoff only when:

1. The payment status is `verified`.
2. The order status is `confirmed`.

Provider acceptance or rejection happens through the provider adapter boundary
after handoff. Provider adapter responses are not payment confirmation and must
not mark payments as verified.

Current implementation state:

- Payment status lifecycle validation is implemented as deterministic domain
  logic.
- Payment model persistence is implemented for minimal payment-safe persisted
  fields through the backend Payment model, repository, and migration.
- Provider-neutral payment webhook signature verification foundation is
  implemented and used by the payment webhook processing endpoint.
- Payment webhook processing creates or updates Payment records after signature
  verification and backend Order/customer/amount/currency validation.
- Verified payment webhook processing confirms eligible draft Orders by
  persisting payment provider reference, backend verification timestamp, and
  confirmed status before attempting paid-order provider handoff orchestration.
- Signed non-verified payment webhook statuses persist only lifecycle-allowed
  Payment state and do not confirm Orders or trigger provider handoff.
- Payment provider references are conflict-checked at the service layer.
  Same-reference events may update the same Order's Payment when the canonical
  lifecycle allows it; references already associated with another Order are
  rejected without mutation.
- Payment provider reference lookup is intentionally scoped/list-based rather
  than globally unique. Repository access returns Payments by provider
  reference as a collection so webhook processing can enforce Order-scoped
  conflict rules instead of relying on an unsafe singleton lookup.
- Durable payment webhook replay/idempotency keys are persisted after
  signature verification and trusted payment-event validation. The current
  generic endpoint returns a replay error without reapplying state. This is a
  pre-production behavior that the Wompi route must replace with the committed-
  duplicate HTTP 200 acknowledgement defined below.
- The current lifecycle implementation treats every `expired` Payment as
  immutable. Wompi implementation must add only the authenticated webhook and
  reconciliation recovery transitions defined in this document; it must not
  make `expired` generally mutable.
- The replay key, Payment mutation, and Order mutation are committed in one
  database transaction before provider handoff is attempted.
- Payment records enforce one non-null payment provider reference per Order at
  the database level. Populated-environment deploys must run the duplicate
  `(order_id, payment_provider_reference)` preflight query documented in
  `docs/architecture/environment-strategy.md` before applying this constraint.
- Payment initialization is implemented as `POST /api/v1/payments` for
  authenticated owners of eligible draft Orders. The endpoint accepts only
  `order_id`, derives amount, currency, ownership, and initial `initiated`
  status from backend Order/OrderItem state, and rejects frontend payment,
  pricing, provider-reference, card-data, status, ownership, or confirmation
  claims.
- Payment initialization returns an existing non-terminal Payment attempt for
  the same eligible draft Order instead of duplicating active attempts.
  Terminal Payment attempts allow a new initialization while leaving prior
  Payment history intact.
- Provider handoff transmission service validates verified payment status,
  confirmed order state, persisted payment verification timestamp, and
  backend-owned provider assignment before payload generation and adapter
  transmission.
- Paid-order provider handoff orchestration delegates eligible confirmed paid
  orders to the provider handoff transmission service after successful payment
  webhook processing.

## Approved Payment Provider Contract

The approved production target is Wompi Web Checkout. The decision and its
alternatives are recorded in
`docs/architecture/adr/0004-wompi-payment-provider-boundary.md`.

This target is pending implementation. Until the required issues land, the
existing `POST /api/v1/payments` response remains provider-neutral metadata and
the generic `POST /api/v1/payments/webhook` remains a deterministic foundation,
not a production Wompi contract.

### Provider Boundary

Payment providers are adapters inside the existing modular monolith. A common
gateway supports:

- initializing a customer checkout handoff
- authenticating and normalizing a provider webhook
- retrieving provider status for reconciliation

The adapter translates provider data. Common application services own
authentication, authorization, backend amount and currency validation, Payment
lifecycle transitions, persistence, Order confirmation, and downstream
fulfillment-provider handoff.

A registry resolves adapters by stable `provider_code`. The configured default
provider is used only for a newly created Payment. Once a Payment exists, every
operation resolves its adapter from the persisted `Payment.provider_code`,
never from the current default.

### Payment Aggregate And Identifiers

A Payment represents one PlacamIA checkout aggregate. It may contain multiple
external provider transactions.

Payment stores:

- `provider_code`: stable adapter identifier, initially `wompi`
- `merchant_reference`: non-sensitive PlacamIA reference stable for the
  Payment aggregate
- `provider_checkout_reference`: optional provider session identifier
- `checkout_expires_at`: optional deadline for starting another transaction
- canonical Payment status, amount, currency, and timestamps

For Wompi Web Checkout, `merchant_reference` is the Wompi payment reference and
is generated as `placamia-payment-{payment_id}` after the Payment id exists.
Wompi does not currently require a separate durable checkout reference, so
`provider_checkout_reference` may be null.

Provider transaction ids are stored in a separate
`payment_provider_transactions` relation with provider status, normalized
status, amount, currency, provider timestamp, and last observation time. A
single scalar transaction id on Payment is not canonical because Wompi retries
can retain one merchant reference while creating another transaction id.

Safe webhook/reconciliation observations are stored in a separate
`payment_provider_events` relation. Event records include a deterministic
provider event/replay reference, linked transaction when known, a payload hash,
and provider/receipt timestamps. Raw provider payloads, signatures, secrets,
card data, and unnecessary customer data are not persisted.

Database uniqueness includes provider identity:

- `(provider_code, merchant_reference)` for Payment aggregates
- `(provider_code, provider_transaction_reference)` for provider transactions
- `(provider_code, provider_event_reference)` for provider events

`Order.payment_provider_reference` records the trusted transaction id that
verified the Order. It is not used as the Payment aggregate identifier.

### Wompi Checkout Initialization

`POST /api/v1/payments` continues to accept only:

```json
{
  "order_id": 42
}
```

The backend owns provider selection, amount, currency, merchant reference,
expiration, return URL, and signature inputs. It rejects non-COP Orders before
creating a Wompi handoff.

For Wompi, initialization:

1. creates or reuses one active Payment safely under concurrent requests
2. persists `provider_code = "wompi"` and the stable merchant reference
3. converts the persisted COP Decimal amount to exact integer cents
4. sets an expiration 30 minutes after initialization
5. signs Wompi's reference, amount, currency, expiration, and integrity secret
   using the provider-required SHA-256 construction
6. returns a normalized redirect handoff to Wompi Web Checkout
7. moves the Payment to `requires_action` only after the handoff is available

Wompi Web Checkout initialization constructs the signed redirect locally; it
does not create a remote Wompi session or make a provider API request. There is
therefore no provider network timeout or retry policy in the initialization
request. Missing configuration, invalid return URL, unsupported currency,
invalid amount conversion, or signature-construction failure returns a safe
provider-initialization error and leaves no new active Payment committed. A
retry reuses the same active Payment and merchant reference.

Successful target response:

```json
{
  "data": {
    "payment_id": 123,
    "order_id": 42,
    "payment_status": "requires_action",
    "amount": "85000.00",
    "currency": "COP",
    "handoff": {
      "type": "redirect",
      "url": "https://checkout.wompi.co/p/?..."
    },
    "checkout_expires_at": "2026-07-22T18:30:00Z"
  }
}
```

The response does not expose `provider_code`, provider records, secret values,
or raw provider data as separate fields. The opaque handoff URL necessarily
contains Wompi's public checkout parameters, including the public key, merchant
reference, amount, currency, expiration, and integrity signature. Repeated
initialization of the same active Payment returns the same merchant reference
and an equivalent signed handoff. Expiration controls starting a transaction;
an already-started asynchronous transaction may remain pending afterward.

### Aggregate-Aware Provider Status

Provider status lookup uses all persisted correlation data:

```python
@dataclass(frozen=True)
class PaymentStatusQuery:
    merchant_reference: str
    provider_checkout_reference: str | None
    provider_transaction_references: tuple[str, ...]
```

The adapter decides which identifiers its provider supports. Wompi's documented
direct transaction lookup uses a transaction id, so reconciliation queries each
known Wompi transaction id. A signed webhook introduces a trusted candidate
transaction id. A transaction id from a customer return remains untrusted and
is ignored by the customer status endpoint. A future explicit reconciliation
command could accept it only as a candidate and would have to query Wompi and
validate merchant reference, amount, and currency before persistence.

The normalized provider result contains all observed transactions and an
aggregate observation. Canonical aggregation follows these rules:

1. Any trusted approved transaction matching persisted Payment amount,
   currency, and merchant reference makes the Payment `verified`.
2. Otherwise, any in-flight transaction makes the Payment `pending`.
3. Otherwise, a declined or failed transaction leaves the Payment
   `requires_action` while the checkout remains retryable.
4. `checkout_expires_at` closes the handoff to new transaction starts. A known
   in-flight transaction remains `pending` after that timestamp.
5. If the handoff expires without a known in-flight or approved transaction,
   the Payment becomes customer-terminal `expired`.
6. A later trusted `PENDING` or `APPROVED` observation that proves the provider
   accepted the transaction before expiration moves `expired` to `pending` or
   `verified`.
7. `failed` and `cancelled` apply only when the aggregate can no longer produce
   a successful transaction under provider or application rules.

For example, transaction A `DECLINED` followed by transaction B `APPROVED`
under the same Wompi reference yields one verified Payment. The first decline
must not prematurely terminalize the Payment aggregate.

For a late approval, persisted provider financial truth wins over checkout
expiration. If the Order remains `draft`, normal verified-payment confirmation
may proceed. If another Payment already confirmed it, the late Payment is still
recorded as verified, Order confirmation fields are not overwritten,
fulfillment handoff is not repeated, and a safe duplicate-payment operations
signal is recorded for separate resolution.

`GET /api/v1/orders/{order_id}/payment-status` returns persisted canonical
state for the authenticated Order owner and does not call Wompi. Reconciliation
is a separate explicit, rate-limited application operation and is not an
external Wompi call on customer polls. If no authenticated provider observation
supplies a transaction id, the backend cannot pretend to reconcile an unknown
Wompi transaction through the documented id lookup; webhook retries and
operational recovery remain the fallback.

### Customer Payment Status Refresh

`GET /api/v1/orders/{order_id}/payment-status` is the customer refresh boundary
planned by #187. It requires authentication, scopes the Order query by the
current customer, accepts no query parameters, and returns only persisted
Payment and Order evidence. Unknown and cross-customer Order ids share the same
non-disclosing not-found response.

The response contains exactly:

```json
{
  "order_id": 42,
  "order_status": "draft",
  "payment_status": "pending",
  "payment_verified_at": null,
  "is_terminal": false,
  "should_poll": true,
  "poll_after_seconds": 3
}
```

`initiated`, `pending`, and `requires_action` are non-terminal and use the fixed
MVP polling hint of three seconds. `verified`, `failed`, `cancelled`, and
`expired` are terminal and return `should_poll = false` with
`poll_after_seconds = null`. An Order with no Payment returns
`payment_status = null`, `is_terminal = false`, `should_poll = false`, and no
polling hint.

For `expired`, terminal is a customer polling instruction rather than a claim
that provider settlement is impossible. A later trusted provider event may
change persisted state to `pending` or `verified`; a later customer read then
returns that newer persisted state.

The endpoint never calls Wompi, applies lifecycle transitions, confirms an
Order, or triggers fulfillment-provider handoff. Every query parameter,
including a returned Wompi transaction id or forged status claim, is rejected
before Order or Payment reads.

### Wompi Webhook And Customer Return

Production Wompi events use:

```text
POST /api/v1/payments/webhooks/wompi
```

The Wompi route verifies the event checksum using the exact ordered event
properties, timestamp, and configured event secret required by Wompi. Only
after authenticity verification may the adapter return a normalized
`PaymentProviderEvent` to the common webhook application service.

The normalized event includes provider code, replay/event reference, merchant
reference, optional checkout reference, transaction id, observed status,
amount, currency, and provider occurrence time. The common service performs
correlation, replay protection, backend amount/currency checks, lifecycle
validation, persistence, Order confirmation, and fulfillment-provider handoff.

The Wompi event payload may not contain a conventional event UUID. The adapter
therefore derives a deterministic replay reference from authenticated event
fields or a cryptographic hash of the exact verified body. Separate Wompi
transactions under one merchant reference must produce separate replay keys.

Wompi webhook HTTP behavior is explicit:

1. Missing or invalid checksum authentication returns non-2xx and performs no
   writes or external side effects.
2. A new authenticated event returns HTTP 200 only after replay key, provider
   transaction/event, Payment, and eligible Order changes commit atomically.
3. An authenticated duplicate whose replay reference and payload hash match an
   already-committed event returns HTTP 200 with
   `{ "status": "already_processed" }`. It performs no mutation and does not
   repeat fulfillment-provider handoff.
4. A reused replay reference with a different payload hash returns a conflict
   response without mutation and emits a safe security signal.
5. Processing failure before commit returns non-2xx so Wompi can retry.

The committed-duplicate response handles a lost original HTTP response without
telling Wompi that a durably processed event failed.

The configured customer return URL is navigation only. Query parameters
returned to the browser, including a transaction id, never verify Payment or
confirm an Order by themselves. The frontend discards those claims and performs
the safe owner-scoped persisted status read without forwarding query parameters.

### Provider Migration Rule

Changing `PAYMENT_PROVIDER_DEFAULT` affects only new Payments. Existing rows
continue using their persisted provider code and provider-specific webhook
route. A future provider can therefore run alongside Wompi without a flag-day
cutover or stranded pending Payments.

Existing provider-neutral rows use this expand/backfill/contract rollout:

1. Add nullable `provider_code` and `merchant_reference` columns and create the
   new transaction/event tables.
2. Backfill all existing Payments with `provider_code = "legacy_generic"` and
   `merchant_reference = "legacy-payment-{payment_id}"`.
3. Preserve existing `payment_provider_reference` and generic webhook replay
   records. Do not manufacture Wompi transaction/event history or reinterpret
   an Order-scoped generic reference as a globally unique provider transaction.
4. Verify target identity uniqueness and absence of nulls, then apply non-null
   and `(provider_code, merchant_reference)` constraints.
5. Keep `legacy_generic` read-only: historical rows remain available to status
   and audit reads, but the registry cannot create a handoff or route them to
   Wompi.
6. Enable `PAYMENT_PROVIDER_DEFAULT = "wompi"` only after the migration,
   backfill, Wompi configuration, and provider-specific routes are ready.

Verified historical Orders retain their existing payment reference and
verification timestamp. Active generic Payments require an explicit operations
decision before a new Wompi Payment is created; they are not silently converted.

## Current Generic Webhook Signature Verification Boundary

Payment webhook authenticity is verified before provider-specific payment
events are interpreted. The MVP verification foundation is provider-neutral and
uses a backend-configured HMAC-SHA256 secret over the exact raw webhook request
body. The signature header format is:

- `sha256=<hex-encoded-hmac-sha256>`

Verification accepts only payloads that:

1. Include a valid signature generated from the raw request body and the
   server-side `PAYMENT_WEBHOOK_SECRET`.
2. Decode to a JSON object.
3. Include a non-empty provider-neutral event identifier in `id` or `event_id`.
4. Are not already present in caller-owned replay/idempotency storage.

Point 4 describes the current generic endpoint, which returns a replay error.
It is not the approved Wompi delivery response. The Wompi implementation must
separate authentication from replay outcome and acknowledge an already-
committed matching duplicate with HTTP 200 as defined above.

Verification returns a trusted provider-neutral webhook result containing the
event id and decoded payload for later payment processing. It must not mark
payments as verified, confirm orders, write `payment_verified_at`, or trigger
provider handoff.

The Path A webhook processing endpoint expects the signed JSON payload to carry
minimal provider-neutral payment event fields under `data`:

- `order_id`: backend Order id referenced by the payment provider
- `customer_id`: optional backend customer id, rejected if present and
  mismatched
- `payment_status`: canonical payment status such as `verified` or `failed`
- `payment_provider_reference`: provider payment reference to persist after
  successful verification
- `amount`: provider-confirmed payment amount
- `currency`: provider-confirmed three-letter currency code

Only a signed, verified-status event whose order id, optional customer id,
amount, and currency match persisted backend Order state may write
`payment_provider_reference`, write `payment_verified_at`, and move the Order
from `draft` to `confirmed`. Same-reference processing for already-confirmed
orders remains compatible for distinct webhook event ids. Durable replay
storage prevents duplicate effects. The current generic route reports a replay
error; the Wompi route acknowledges an already-committed matching duplicate
with HTTP 200. Conflicting replay content, duplicate references, or mismatched
payment details are rejected without mutation.

Invalid, missing, malformed, or conflicting-replay webhooks must be rejected
before any payment, order, checkout, or provider handoff mutation. An
authenticated matching replay of an already-committed Wompi event is
acknowledged without mutation. Frontend payment claims inside a signed payload
are still data only; they are not payment confirmation and must not create paid,
confirmed, or handoff-eligible state.

After a valid webhook confirms payment, the endpoint attempts provider handoff
through the paid-order handoff orchestration boundary. A failed handoff does
not reject, roll back, or invalidate payment confirmation: the Order remains
`confirmed`, payment confirmation fields remain intact, provider handoff
success fields remain empty, and the order is safe for later retry.

Webhook secrets must come from backend configuration. Secrets, raw sensitive
payloads, and full payment data must not be logged by verification code.

## Related Endpoints

- POST /api/v1/payments
- POST /api/v1/payments/webhook
- POST /api/v1/payments/webhooks/wompi (approved target; pending implementation)
- GET /api/v1/orders/{order_id}/payment-status (planned by #187)

See `docs/api/endpoint-structure.md`.

Provider adapter boundary:

- `docs/planning/provider-adapter-contract.md`
- `docs/architecture/adr/0004-wompi-payment-provider-boundary.md`

## Child Issues

- #62 Define payment status lifecycle
- #53 Implement Path A payment webhook signature verification test foundation

## Related Security Milestone

- #53 Add payment webhook signature verification test foundation

## Future Issues

- #186: implement the Wompi Web Checkout initialization handoff documented
  above.
- #187: implement the authenticated customer Payment-status read and approved
  reconciliation behavior documented above.
- Future issue required: implement the provider-specific Wompi webhook route,
  transaction/event persistence, translation, and migration from the current
  generic webhook foundation.
- Future issue required: make payment initialization concurrency-safe before it
  creates external provider payment sessions. The current provider-neutral
  endpoint is sequentially idempotent, but simultaneous first requests can both
  observe no active Payment and create separate `initiated` rows.
- Future issue required: add payment-provider-specific secret and sensitive
  payload examples to audit redaction tests when the real provider contract
  documents concrete header names, secret fields, tokens, or payload keys.

## Constraints

- Do not store card data.
- Do not trust frontend payment confirmation.
- Do not mark orders as paid without verified payment-provider confirmation.
- Do not trigger provider adapter handoff until payment is verified.
- Do not record provider acceptance or rejection outside the provider adapter
  boundary.
- Do not wait for provider acceptance before confirming customer payment.
- Do not initialize payment for inactive, unavailable, manual-quote-only, or
  non-priceable checkout items.
- Do not treat provider adapter acceptance or rejection as payment
  verification.
- Do not let frontend payment return claims produce paid, verified, confirmed,
  or handoff-eligible state.
- Do not let webhook signature verification by itself mutate payment, order,
  checkout, or provider handoff state.
- Do not treat payment provider references as globally unique application
  identifiers. Conflict checks must remain Order-scoped and explicit.
- Do not resolve an existing Payment through the current default provider.
- Do not treat one external transaction as the Payment aggregate.
- Do not terminalize a retryable Payment solely because one Wompi transaction
  was declined or failed.
- Do not treat `checkout_expires_at` as proof that a provider-accepted
  transaction cannot settle. Trusted late `PENDING` and `APPROVED` observations
  may recover an expired Payment through the narrow documented transitions.
- Do not treat the Wompi customer return as payment confirmation.

## Security Considerations

Payments are one of the highest-risk MVP areas.

Required protections:

- signature verification
- replay protection where practical
- no sensitive payment data in logs
- no card storage
- strict provider payload validation
- no order state mutation on invalid webhook
- no provider handoff on failed, invalid, or missing payment events
- authenticated committed webhook duplicates return HTTP 200 without repeating
  Payment, Order, event, transaction, or provider-handoff effects
- no provider acceptance or rejection from raw frontend payloads or unverified
  payment events

See docs/architecture/security.md and docs/architecture/testing.md.

## Testing Requirements

Payments must include tests for:

- valid webhook confirms payment
- invalid signature rejected
- missing signature rejected
- authenticated replay after a committed event returns HTTP 200
  `already_processed` and does not duplicate state changes or side effects
- simulated lost original response followed by provider retry receives HTTP 200
  and exact before/after persistence equality
- same replay reference with a different payload hash is rejected without
  mutation and emits a safe conflict signal
- failed payment does not confirm order
- frontend confirmation alone does not mark order as paid
- invalid webhook does not mutate order/payment state
- provider handoff is not triggered by invalid or failed payment
- provider handoff is triggered only through the provider adapter after
  verified payment
- provider acceptance/rejection is recorded only through the provider adapter
  boundary
- Provider acceptance is not required to mark a verified payment as paid
- one merchant reference can store and aggregate multiple provider transactions
- a declined transaction followed by an approved retry verifies one Payment
- expiration blocks new starts but does not override a known pending transaction
- trusted approval after `checkout_expires_at`, including after persisted
  `expired`, verifies Payment and confirms a still-draft Order exactly once
- late approval after another Payment confirmed the Order records financial
  truth and an operations signal without reconfirmation or duplicate handoff
- provider-specific webhook signatures and replay references are validated
- changing the default provider does not change existing Payment routing
- legacy generic Payment backfill preserves historical references and never
  routes grandfathered rows to Wompi
- customer return data cannot verify a Payment without trusted reconciliation

## Done When

- Payment lifecycle is documented
- Payment records are persisted safely
- Payment-provider confirmation is verified and processed through trusted
  backend paths
- Orders are confirmed only after verified payment
- Confirmed paid orders can be handed off through the provider adapter without
  treating provider responses as payment confirmation
- Tests cover successful and rejected flows
