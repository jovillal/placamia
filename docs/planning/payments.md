# Payments

## Goal

Verify customer payment before an order can move into confirmed fulfillment.

Payments are a security-critical boundary. The backend must never fulfill an
order based only on frontend confirmation.

## Core Principles

- Do not store card data.
- Use a payment provider for payment processing.
- Store only payment references, statuses, order id, amount, currency, and timestamps.
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
8. Confirmed order becomes eligible for provider adapter handoff
9. Provider adapter records provider acceptance or rejection after handoff

## Scope

- Payment model
- Payment status lifecycle
- Payment provider reference
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
- `failed`: payment provider reported failed payment.
- `cancelled`: payment provider or customer cancelled the payment attempt.
- `expired`: payment provider reported the attempt expired.

Terminal payment statuses:

- `verified`
- `failed`
- `cancelled`
- `expired`

Allowed transitions:

- `initiated -> pending` when the payment provider reports pending processing.
- `initiated -> requires_action` when the payment provider requires customer
  action.
- `initiated|pending|requires_action -> verified` only after trusted,
  verified payment-provider confirmation.
- `pending <-> requires_action` when the payment provider changes the required
  customer/provider processing state.
- `initiated|pending|requires_action -> failed` when the payment provider
  reports failed payment.
- `initiated|pending|requires_action -> cancelled` when the payment provider
  reports cancellation.
- `initiated|pending|requires_action -> expired` when the payment provider
  reports expiration.

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
must not confirm an order. Replayed payment events must not duplicate state
changes; concrete replay/idempotency storage is defined by later webhook work.

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
- Provider-neutral payment webhook signature verification foundation is
  implemented and used by the payment webhook processing endpoint.
- Payment webhook processing confirms eligible draft Orders by persisting
  payment provider reference, backend verification timestamp, and confirmed
  status without triggering provider handoff.
- Provider handoff transmission service validates verified payment status,
  confirmed order state, persisted payment verification timestamp, and
  backend-owned provider assignment before payload generation and adapter
  transmission.
- Payment model persistence, payment initialization, durable webhook
  replay/idempotency persistence, and automatic provider handoff orchestration
  remain future work.

## Webhook Signature Verification Boundary

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
from `draft` to `confirmed`. Same-reference replays for already-confirmed
orders are idempotent; conflicting duplicate references or mismatched payment
details are rejected without mutation.

Invalid, missing, malformed, or replayed webhooks must be rejected before any
payment, order, checkout, or provider handoff mutation. Frontend payment claims
inside a signed payload are still data only; they are not payment confirmation
and must not create paid, confirmed, or handoff-eligible state.

Webhook secrets must come from backend configuration. Secrets, raw sensitive
payloads, and full payment data must not be logged by verification code.

## Related Endpoints

- POST /api/v1/payments
- POST /api/v1/payments/webhook

See `docs/api/endpoint-structure.md`.

Provider adapter boundary:

- `docs/planning/provider-adapter-contract.md`

## Child Issues

- #62 Define payment status lifecycle
- #53 Implement Path A payment webhook signature verification test foundation

## Related Security Milestone

- #53 Add payment webhook signature verification test foundation

## Future Issues

- Future issue required: create Payment model, migration, and tests
- Future issue required: create payment initialization endpoint
- Future issue required: persist payment transition idempotency/replay keys
- Future issue required: trigger provider handoff after confirmed payment

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

## Security Considerations

Payments are one of the highest-risk MVP areas.

Required protections:

- signature verification
- replay protection where practical
- no sensitive payment data in logs
- no card storage
- strict provider payload validation
- no order state mutation on invalid webhook
- no provider handoff on failed, invalid, missing, or replayed payment events
- no provider acceptance or rejection from raw frontend payloads or unverified
  payment events

See docs/architecture/security.md and docs/architecture/testing.md.

## Testing Requirements

Payments must include tests for:

- valid webhook confirms payment
- invalid signature rejected
- missing signature rejected
- replayed event does not duplicate state changes
- failed payment does not confirm order
- frontend confirmation alone does not mark order as paid
- invalid webhook does not mutate order/payment state
- provider handoff is not triggered by invalid or failed payment
- provider handoff is triggered only through the provider adapter after
  verified payment
- provider acceptance/rejection is recorded only through the provider adapter
  boundary
- Provider acceptance is not required to mark a verified payment as paid

## Done When

- Payment lifecycle is documented
- Payment records are persisted safely
- Payment-provider confirmation is verified and processed through trusted
  backend paths
- Orders are confirmed only after verified payment
- Confirmed paid orders can be handed off through the provider adapter without
  treating provider responses as payment confirmation
- Tests cover successful and rejected flows
