# PlacamIA Mobile Placeholder

This is the deliberately thin Expo placeholder for the Path A MVP customer
journey. It reflects `docs/planning/mobile-placeholder.md` and must remain
static/mock-only until the corresponding backend contracts are implemented.

## Boundary

- No real authentication flow, embedded credentials, bearer tokens, persisted
  sessions, or backend-auth bypass.
- No production API base URL or production customer data.
- No persisted customer, payment, order, or provider data.
- No checkout submission against live backend state.
- No payment provider SDK, payment session, card collection, or raw provider
  payload handling.
- No direct mobile calls to payment webhook, provider, operator, or admin
  endpoints.
- No static legal copy presented as production cancellation/refund policy.
- No real-time payment confirmation claims without a documented customer
  payment-status refresh contract.

## Local Setup

Install dependencies from this directory:

```bash
npm install
```

Run validation:

```bash
npm run validate
```

Start the Expo placeholder:

```bash
npm run start
```

For web preview:

```bash
npm run web
```

The placeholder uses static/mock data from
`src/placeholderContract.json`. Update that file only when the approved screen
map changes.
