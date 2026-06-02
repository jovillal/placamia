# Provider Fulfillment Flow

## Purpose

Define how a paid PlacamIA order is handed off to Relieves de Colombia and
tracked through manufacturing, pickup, shipment, and delivery.

This flow is downstream of verified customer payment. It is not an RFQ flow and
must not be used to block checkout for direct-checkout MVP items.

## Flow Diagram

```mermaid
flowchart TD
    B1[Confirmed paid order] --> B2[Prepare provider payload]
    B2 --> D1[(Order + OrderItems + Design)]
    B2 --> B3[Send paid order to Relieves]

    B3 --> P1[Relieves receives order]
    P1 --> P2{Accept order?}

    P2 -->|yes| B4[Mark accepted]
    B4 --> P3[Relieves manufactures order]
    P3 --> P4[Relieves prepares package]
    P4 --> P5[Relieves prints and attaches QR]
    P5 --> C1[Carrier scans QR at pickup]
    C1 --> B5[Mark shipped]
    B5 --> C2[Carrier delivers package]
    C2 --> B6[Mark delivered]

    P2 -->|no| B7[Mark provider rejection]
    B7 --> B8[Start cancellation or refund handling]

    B3 -. transmission failure .-> R1[Retry idempotently]
    C1 -. QR unavailable .-> R2[Operator records shipment event]
```

## Status Mapping

```mermaid
stateDiagram-v2
    confirmed --> sent_to_provider: paid-order handoff sent
    sent_to_provider --> accepted: Relieves accepts
    sent_to_provider --> cancelled: Relieves rejects
    accepted --> in_production: production starts
    in_production --> ready_for_pickup: package prepared with QR
    ready_for_pickup --> shipped: carrier pickup scan
    shipped --> delivered: delivery confirmed
```

## Rules

- Provider payloads must be generated from persisted backend data.
- Raw frontend payloads must never be forwarded to Relieves.
- The paid order is the production trigger.
- Relieves acceptance happens after verified payment in the direct-checkout MVP
  path.
- Provider transmission should be idempotent where possible.
- Shipment should be recorded from the QR pickup scan once the selected carrier
  integration validates that mechanism.
- Until QR pickup is technically validated, an operator may record the shipment
  event as the fallback.

## Operational Notes

PlacamIA owns customer notifications, customer complaints, customer refunds, and
customer-facing tracking. Relieves owns manufacturing and package preparation.

Customer invoicing, Relieves invoicing, PlacamIA payment to Relieves, and SLA
consequences are business/accounting processes that must be documented before
they are automated.

## Related Planning Docs

- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/planning/provider.md`

## Security Notes

- Do not expose internal order fields in provider payloads.
- Do not log sensitive payment data, customer secrets, or full webhook payloads.
- Failed provider transmission must not corrupt order state.
- Repeated handoff attempts must not duplicate provider orders.
