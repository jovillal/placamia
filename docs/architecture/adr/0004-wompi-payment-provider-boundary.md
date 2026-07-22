# ADR 0004: Wompi payment provider boundary

## Status

Accepted on 2026-07-22. Implementation remains pending.

## Context

PlacamIA has provider-neutral Payment lifecycle, initialization, webhook, and
replay-protection foundations. It does not yet create a real customer payment
handoff or process a production payment-provider webhook.

The first production integration must support Colombia, COP, a mobile-first
redirect flow, backend-owned prices, and no card-data handling by PlacamIA. It
must also avoid coupling the Payment domain to one provider. This matters
because Wompi can create multiple transaction ids for retries that retain the
same merchant reference.

In this ADR, **payment provider** means Wompi or a future payment processor.
The existing **fulfillment provider** adapter remains a separate downstream
boundary that receives confirmed paid Orders.

## Decision

### Initial Provider And Checkout Mode

Use Wompi Web Checkout as the first production payment provider. The customer
is redirected to Wompi's hosted checkout, so PlacamIA does not collect or store
card or bank credentials.

The production decision does not imply that merchant onboarding, production
credentials, or commercial approval are complete. Those are deployment
prerequisites, not reasons to change the application boundary.

PlacamIA supports COP in the Wompi adapter. A Payment whose backend-owned Order
uses another currency must be rejected before a Wompi handoff is created.

### Modular Monolith Boundary

Keep payment orchestration inside the FastAPI modular monolith. Do not create a
separately deployed payment service for the MVP.

The payment module owns:

- Payment lifecycle and persistence
- authenticated customer payment initialization
- provider selection and registry resolution
- provider webhook routing and normalized event processing
- reconciliation orchestration
- Payment-to-Order confirmation

Each provider adapter owns only provider mechanics:

- customer handoff initialization
- provider request signing and authentication
- provider webhook authenticity verification and parsing
- provider status retrieval
- translation between provider statuses and normalized observations

The fulfillment-provider adapter must not implement any of these payment
responsibilities.

### Gateway And Registry

Use a narrow provider gateway shaped around PlacamIA use cases:

```python
class PaymentProviderGateway(Protocol):
    async def initialize_checkout(
        self,
        request: CheckoutRequest,
    ) -> CheckoutSession: ...

    def verify_webhook(
        self,
        raw_body: bytes,
        headers: Mapping[str, str],
    ) -> PaymentProviderEvent: ...

    async def get_payment_status(
        self,
        query: PaymentStatusQuery,
    ) -> PaymentProviderStatus: ...
```

`initialize_checkout()` returns a normalized customer handoff. For the MVP,
the handoff is a discriminated redirect value rather than a generic pair of
nullable URL and token fields:

```python
@dataclass(frozen=True)
class RedirectCheckoutHandoff:
    type: Literal["redirect"]
    url: str


@dataclass(frozen=True)
class CheckoutSession:
    merchant_reference: str
    provider_checkout_reference: str | None
    handoff: RedirectCheckoutHandoff
    expires_at: datetime | None
```

A future provider may add another handoff variant without changing the Payment
domain to assume that all providers use signed URLs.

The normalized contracts use provider observations rather than authoritative
domain commands:

```python
@dataclass(frozen=True)
class CheckoutRequest:
    merchant_reference: str
    amount: Decimal
    currency: str
    customer_email: str
    return_url: str
    expires_at: datetime | None


@dataclass(frozen=True)
class ProviderTransactionStatus:
    provider_transaction_reference: str
    provider_status: str
    observed_status: PaymentStatus
    amount: Decimal | None
    currency: str | None
    occurred_at: datetime | None


@dataclass(frozen=True)
class PaymentProviderEvent:
    provider_code: str
    event_reference: str
    merchant_reference: str
    provider_checkout_reference: str | None
    provider_transaction_reference: str | None
    provider_status: str
    observed_status: PaymentStatus
    amount: Decimal | None
    currency: str | None
    occurred_at: datetime | None


@dataclass(frozen=True)
class PaymentProviderStatus:
    merchant_reference: str
    provider_checkout_reference: str | None
    transactions: tuple[ProviderTransactionStatus, ...]
    observed_aggregate_status: PaymentStatus
```

The application service remains responsible for deciding whether an observed
status is valid for the current persisted lifecycle and whether it can confirm
an Order.

The registry maps a stable `provider_code` to an adapter and exposes the
configured default. It contains no lifecycle or routing rules. The default is
used only when creating a new Payment. Every later operation resolves the
adapter from the `provider_code` persisted on that Payment.

Changing the default therefore affects new Payments only. Existing Wompi
Payments continue to accept Wompi webhooks and reconciliation after another
provider becomes the default.

### Payment And Provider Transaction Identity

A PlacamIA Payment is one checkout aggregate, not one provider transaction.
Persist these stable identifiers on Payment:

- `provider_code`
- `merchant_reference`
- optional `provider_checkout_reference`
- optional `checkout_expires_at`

For Wompi Web Checkout:

- `merchant_reference` is generated by PlacamIA and remains stable for the
  Payment aggregate
- `provider_checkout_reference` is absent unless Wompi later exposes a durable
  session-level identifier
- each Wompi transaction id is a `provider_transaction_reference`

Do not use one canonical `provider_transaction_reference` column on Payment.
Persist external transactions separately because one merchant reference may
have several declined, pending, or approved transaction ids.

The target persistence boundary is:

```text
payments
  id, order_id, provider_code, merchant_reference,
  provider_checkout_reference, status, amount, currency,
  checkout_expires_at, verified_at, created_at, updated_at

payment_provider_transactions
  id, payment_id, provider_code, provider_transaction_reference,
  provider_status, normalized_status, amount, currency, provider_created_at,
  last_observed_at

payment_provider_events
  id, payment_id, payment_provider_transaction_id, provider_code,
  provider_event_reference, payload_hash, provider_occurred_at,
  received_at
```

Enforce uniqueness for `(provider_code, merchant_reference)` on Payment,
`(provider_code, provider_transaction_reference)` on provider transactions, and
`(provider_code, provider_event_reference)` on provider events. Raw provider
payloads, signatures, credentials, card data, and unnecessary customer data are
not persisted.

`Order.payment_provider_reference` may continue to record the specific trusted
transaction that verified the Order. It is not the Payment aggregate id and is
not used to find every retry.

### Aggregate-Aware Status

Status lookup must not assume one checkout equals one provider transaction:

```python
@dataclass(frozen=True)
class PaymentStatusQuery:
    merchant_reference: str
    provider_checkout_reference: str | None
    provider_transaction_references: tuple[str, ...]
```

The adapter chooses the identifiers supported by its provider. Wompi status
retrieval queries the known transaction ids and returns normalized transaction
observations plus an aggregate observation.

Aggregate rules are deterministic:

1. A trusted approved transaction with matching amount, currency, and merchant
   reference makes the Payment `verified`.
2. Otherwise, any in-flight transaction makes the Payment `pending`.
3. A declined or failed external transaction does not terminalize the Payment
   while the checkout can still be retried; the Payment remains
   `requires_action`.
4. The Payment becomes `expired`, `failed`, or `cancelled` only when the
   aggregate can no longer produce a successful transaction under documented
   provider or application rules.

The provider adapter reports observations. The application service validates
the canonical lifecycle transition, backend-owned amount and currency, Order
eligibility, and transactional persistence before confirming an Order.

### Wompi Initialization

For a new active Payment, PlacamIA:

1. selects and persists `provider_code = "wompi"`
2. generates a non-sensitive stable merchant reference from the Payment id
3. uses the persisted Order amount and converts it to integer COP cents
4. sets a backend-owned checkout expiration
5. calculates Wompi's SHA-256 integrity signature with the integrity secret
6. returns the hosted Web Checkout URL through the normalized redirect handoff

The public response remains provider-neutral. It exposes the Payment and Order
ids, canonical status, backend-owned amount and currency, handoff type and URL,
and expiration. It exposes no Wompi secret, raw provider payload, or internal
provider record. The opaque handoff URL necessarily contains Wompi's public
checkout parameters, merchant reference, and integrity signature.

Repeated initialization of the same active Payment returns the same persisted
merchant reference and equivalent handoff. Concurrency control must prevent two
simultaneous requests from creating separate active Payment aggregates or
external handoffs for one Order.

### Webhooks, Returns, And Reconciliation

Use provider-specific webhook routes:

```text
POST /api/v1/payments/webhooks/wompi
POST /api/v1/payments/webhooks/{future-provider}
```

The route selects the verifier from its path, verifies the provider-specific
signature over the exact request representation required by that provider,
and emits a normalized `PaymentProviderEvent`. A common application service
then correlates the event, stores safe event and transaction metadata, applies
replay protection, validates lifecycle changes, and confirms eligible Orders.

Wompi event identity may not be a conventional event UUID. The adapter must
produce a deterministic replay key from authenticated provider event fields or
a cryptographic hash of the exact verified body. The replay key must distinguish
separate transactions under the same merchant reference.

The customer return URL is navigation only. A returned Wompi transaction id is
untrusted and must never directly verify a Payment or confirm an Order. The
customer status endpoint ignores it and reads persisted state. A future
explicit reconciliation command could use it only as a candidate for a
backend-to-Wompi status query whose result is validated against the persisted
Payment.

Customer status reads use the owned Order id and return persisted canonical
state. Provider reconciliation is a separate explicit, throttled application
operation; it is not an external request on the customer polling path.

### Configuration And Secrets

Provider selection and credentials come from backend runtime configuration.
The planned Wompi variables are documented in
`docs/architecture/environment-strategy.md`.

Public and private provider values remain distinct. Public keys may be used to
construct the hosted checkout, while integrity and event secrets remain
backend-only. Secrets and full signed URLs must not be logged.

## Consequences

### Positive

- Wompi can be replaced or run alongside another provider without rewriting
  Payment lifecycle and Order confirmation.
- Existing Payments continue using their persisted provider during a gradual
  migration.
- Wompi retries with multiple transaction ids are represented without
  overwriting history or prematurely failing the Payment aggregate.
- Hosted checkout keeps card and bank credentials outside PlacamIA.
- Provider-specific webhook routes keep signature verification explicit and
  auditable.

### Negative

- The initial integration requires new Payment identity fields, transaction and
  event persistence, migrations, and concurrency control.
- Provider adapters must normalize different status and handoff semantics.
- Reconciliation requires operational throttling and monitoring in addition to
  webhook processing.
- Switching providers still requires an adapter, contract tests, credentials,
  webhook configuration, and production validation; the boundary reduces this
  work but cannot eliminate it.

## Alternatives Considered

- **Wompi-specific logic in routes and Payment columns:** rejected because it
  would couple public APIs, persistence, and lifecycle rules to one provider.
- **One transaction reference on Payment:** rejected because Wompi retries can
  produce multiple transaction ids under one merchant reference.
- **One generic webhook route selected by the current default provider:**
  rejected because old Payments must remain processable after the default
  changes and each provider has different authentication semantics.
- **A separately deployed payment microservice:** rejected for MVP because it
  adds deployment, transaction, observability, and failure-mode complexity
  before team or scale constraints justify extraction.
- **Direct card collection:** rejected because PlacamIA must not store or handle
  raw card credentials.

## Review Trigger

Revisit this ADR when a second payment provider is implemented, Wompi changes
its hosted checkout or event contract, non-COP checkout becomes required, or
payment scale and team ownership justify extracting the module into a separate
service.

## References

- [Wompi Web Checkout](https://docs.wompi.co/docs/colombia/widget-checkout-web/)
- [Wompi events](https://docs.wompi.co/docs/colombia/eventos/)
- [Wompi transactions and status lookup](https://docs.wompi.co/docs/colombia/transacciones/)
- [Wompi payment retries](https://docs.wompi.co/docs/colombia/reintento-de-pago/)
- `docs/planning/payments.md`
- `docs/flows/checkout-flow.md`
