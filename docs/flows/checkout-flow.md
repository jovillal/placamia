# Checkout Flow

## Purpose

Define the process from pricing confirmation to order creation and payment verification.

This flow is security-critical.

## Flow Diagram

```mermaid
flowchart TD
    U1[User requests checkout] --> B1[Validate design and pricing]

    B1 --> D1[(Design)]
    B1 --> D2[(Pricing rules)]

    B1 --> B2[Create draft order]
    B2 --> D3[(Order)]

    B2 --> B3[Initialize payment]

    U2[User completes payment] --> B4[Receive payment webhook]

    B4 --> B5[Verify signature]

    B5 -->|valid| B6[Confirm order]
    B5 -->|invalid| R1[Reject payment]

    B6 --> D3
```
---

### Key Rules
- Orders must be created from backend-validated data
- Frontend price must be ignored
- Payment must be verified via provider webhook

---

## Constraints
- No order is confirmed without verified payment
- Invalid payments must not mutate order state
- Replayed payment events must not duplicate state changes

---

## Related Planning Docs
- `docs/planning/pricing.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`

---

## Security Notes
- Reject invalid signatures
- Do not trust frontend confirmation
- Ensure idempotency in payment handling