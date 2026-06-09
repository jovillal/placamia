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

## Related Endpoints

- POST /api/v1/payments
- POST /api/v1/payments/webhook

See `docs/api/endpoint-structure.md`.

Provider adapter boundary:

- `docs/planning/provider-adapter-contract.md`

## Child Issues

- #62 Define payment status lifecycle

## Related Security Milestone

- #53 Add payment webhook signature verification test foundation

## Future Issues

- Future issue required: create Payment model, migration, and tests
- Future issue required: create payment initialization endpoint
- Future issue required: create payment webhook endpoint
- Future issue required: add replay/idempotency tests
- Future issue required: add order confirmation transition after verified
  payment
- Future issue required: persist payment transition idempotency/replay keys

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
- Payment-provider confirmation is verified
- Orders are confirmed only after verified payment
- Tests cover successful and rejected flows
