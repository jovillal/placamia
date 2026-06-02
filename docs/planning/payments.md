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
- Provider acceptance or rejection happens after verified payment and must not
  be treated as a payment confirmation.

## Flow

1. User starts checkout
2. Backend creates or prepares payment request
3. User completes payment through provider flow
4. Provider sends confirmation/webhook
5. Backend verifies signature and payload
6. Backend updates Payment state
7. Backend moves Order from `draft` to `confirmed`
8. Confirmed order becomes eligible for provider handoff
9. Assigned provider accepts or rejects the paid order after handoff

## Scope

- Payment model
- Payment status lifecycle
- Payment provider reference
- Payment webhook/confirmation endpoint
- Signature validation
- Payment-to-order transition

## Related Endpoints

- POST /api/v1/payments
- POST /api/v1/payments/webhook

See `docs/api/endpoint-structure.md`.

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

## Constraints

- Do not store card data.
- Do not trust frontend payment confirmation.
- Do not mark orders as paid without verified payment-provider confirmation.
- Do not trigger provider handoff until payment is verified.
- Do not wait for provider acceptance before confirming customer payment.
- Do not initialize payment for inactive, unavailable, manual-quote-only, or
  non-priceable checkout items.

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
- Provider acceptance is not required to mark a verified payment as paid

## Done When

- Payment lifecycle is documented
- Payment records are persisted safely
- Payment-provider confirmation is verified
- Orders are confirmed only after verified payment
- Tests cover successful and rejected flows
