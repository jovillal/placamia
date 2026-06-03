# Provider Fulfillment Flow

## Purpose

Define how a paid PlacamIA order is handed off through the provider adapter
boundary to the assigned manufacturing provider and tracked through
manufacturing, pickup, shipment, and delivery.

This flow is downstream of verified customer payment. It is not an RFQ flow and
must not be used to block checkout for direct-checkout MVP items.

## Flow Diagram

```mermaid
flowchart TD
    B1[Confirmed paid order] --> B2[Prepare provider payload]
    B2 --> D1[(Order + OrderItems + Design)]
    B2 --> A1[Provider adapter handoff]
    A1 --> B3[Send paid order to assigned provider]

    B3 --> P1[Provider receives order]
    P1 --> P2{Accept order?}

    P2 -->|yes| A2[Adapter records acceptance]
    A2 --> B4[Mark accepted]
    B4 --> P3[Provider manufactures order]
    P3 --> P4[Provider prepares package]
    P4 --> P5[Provider prints and attaches QR]
    P5 --> C1[Carrier scans QR at pickup]
    C1 --> B5[Mark shipped]
    B5 --> C2[Carrier delivers package]
    C2 --> B6[Mark delivered]

    P2 -->|no| A3[Adapter records rejection]
    A3 --> B7[Mark provider rejection]
    B7 --> B8[Start cancellation or refund handling]

    A1 -. transmission failure .-> R1[Retry idempotently]
    C1 -. QR unavailable .-> R2[Operator records shipment event]
```

## Status Mapping

```mermaid
stateDiagram-v2
    confirmed --> sent_to_provider: adapter handoff sent after verified payment
    sent_to_provider --> accepted: adapter records provider acceptance
    sent_to_provider --> cancelled: adapter records provider rejection
    accepted --> in_production: production starts
    in_production --> ready_for_pickup: package prepared with QR
    ready_for_pickup --> shipped: carrier pickup scan
    shipped --> delivered: delivery confirmed
```

## Rules

- Provider payloads must be generated from persisted backend data.
- Raw frontend payloads must never be forwarded to a provider.
- The paid order is the production trigger.
- Provider handoff must happen only through the provider adapter boundary after
  verified payment in the direct-checkout MVP path.
- Provider acceptance or rejection must be recorded through the provider adapter
  boundary.
- Provider transmission should be idempotent where possible.
- Shipment should be recorded from the QR pickup scan once the selected carrier
  integration validates that mechanism.
- Until QR pickup is technically validated, an operator may record the shipment
  event as the fallback.

## Operational Notes

PlacamIA owns customer notifications, customer complaints, customer refunds, and
customer-facing tracking. The assigned provider owns manufacturing and package
preparation.

Customer invoicing, provider invoicing, PlacamIA payment to providers, and SLA
consequences are business/accounting processes that must be documented before
they are automated.

## Related Planning Docs

- `docs/planning/provider-adapter-contract.md`
- `docs/planning/orders.md`
- `docs/planning/payments.md`
- `docs/planning/provider.md`

## Security Notes

- Do not expose internal order fields in provider payloads.
- Do not log sensitive payment data, customer secrets, or full webhook payloads.
- Failed provider transmission must not corrupt order state.
- Repeated handoff attempts must not duplicate provider orders.
