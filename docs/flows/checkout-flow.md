# Checkout Flow

## Purpose

Define the process from backend pricing to order creation and payment
verification.

This flow is security-critical.

The implemented checkout path is direct checkout for fully parametrizable
Products. Checkout must not wait for provider quote confirmation, but it must
reject any item that cannot be priced and validated by backend-owned rules.
Fixed-content Kits and persisted Designs have pricing previews; their order
creation paths remain separate work and do not enter this flow.

## Flow Diagram

```mermaid
flowchart TD
    U1[User requests checkout] --> B1[Validate direct-checkout eligibility]

    B1 --> D1[(Product catalog state)]
    B1 --> D2[(Pricing rules and provider adapter responses)]

    B1 --> B2[Recalculate backend price]
    B2 --> B3[Show cancellation and refund terms]
    B3 --> U2[User accepts terms and confirms checkout]

    U2 --> B4[Create draft order]
    B4 --> D3[(Order)]

    B4 --> B5[Initialize payment]

    U3[User completes payment] --> B6[Receive payment webhook]

    B6 --> B7[Verify signature and replay safety]

    B7 -->|valid| B8[Confirm order]
    B7 -->|invalid| R1[Reject payment without mutation]

    B8 --> D3
    B8 --> B9[Prepare paid-order handoff]
    B9 --> A1[Provider adapter handoff]
    A1 --> P1[Send paid order to assigned provider]

    B1 -. not eligible .-> R2[Reject checkout]
    B2 -. invalid pricing input .-> R3[Reject checkout]
```
---

### Key Rules
- Orders must be created from backend-validated data
- Frontend price must be ignored
- Checkout eligibility in this implemented flow is limited to active,
  fully parametrizable, backend-priceable Products.
- Fixed-content Kit pricing is public, but Kit order creation remains separate
  work.
- Persisted Design pricing is owner-scoped, revalidates current TemplateFields,
  and derives its temporary amount through `Design -> Template -> Product`, but
  it does not create an Order or enter payment initialization.
- Manual quotes and provider-confirmed pricing are out of scope for the direct
  checkout MVP path
- Cancellation and refund terms must be shown before payment
- Payment initialization must use backend-owned draft Order and OrderItem
  snapshot state; it must not accept frontend amount, currency, status,
  provider-reference, card-data, ownership, or confirmation claims
- Payment must be verified via provider webhook
- Paid-order provider handoff happens through the provider adapter boundary
  only after verified payment

---

## Constraints
- No order is confirmed without verified payment
- Payment initialization creates or returns only an active Payment attempt; it
  does not confirm orders or trigger provider handoff
- Invalid payments must not mutate order state
- Replayed payment events must not duplicate state changes
- Manufacturing provider confirmation must not be used as a pre-payment
  checkout gate in the MVP direct-checkout path
- Products or configurations that require manual provider confirmation must be
  unavailable for direct checkout until canonical docs define their behavior

---

## Related Planning Docs
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/planning/provider-adapter-contract.md`
- `docs/planning/provider.md`

---

## Security Notes
- Reject invalid signatures
- Do not trust frontend confirmation
- Do not trust frontend-supplied price, availability, quantity limits, or
  ownership claims
- Do not store card data during payment initialization
- Ensure idempotency in payment handling
