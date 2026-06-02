# Legal and Business Questions

(Discovery Phase / Non-Canonical)

## Purpose

This document tracks legal, tax, liability, and business-structure questions
that must be answered by qualified legal/accounting/business advisors before
implementation depends on them.

These questions should not be resolved by engineering guesses.

## Open Questions

### 1. Customer Contract, Merchant of Record, and Seller of Record

**Question:** In the Path A direct-checkout flow, is the customer contract with
PlacamIA, with Relieves, or with PlacamIA acting as a marketplace or
intermediary?

**Needs legal/business answer:** Yes.

**Why this matters:** This decision affects checkout, invoices, taxes, refunds,
chargebacks, cancellation terms, provider liability, customer support, dispute
handling, and terms of service.

**Current product-design assumption:** PlacamIA owns the customer checkout,
transaction experience, notifications, complaints, and refund coordination.
Relieves acts as manufacturing provider and invoices PlacamIA. The legal
merchant-of-record and seller-of-record decision is still unresolved.

**Implementation guardrail:** Do not finalize payment, invoice, refund,
provider liability, tax, or customer-contract behavior until this question has
been answered by someone with appropriate legal/accounting background.
Prototype flows may continue with fake or manual payment states, but production
payment/checkout implementation should be blocked until this question is
answered.

### 2. Provider Invoice, Payout, and SLA Consequences

**Question:** When should Relieves invoice PlacamIA, when should PlacamIA pay
Relieves, and what happens commercially if Relieves rejects or fails an accepted
paid order?

**Needs legal/business answer:** Yes.

**Why this matters:** Path A charges the customer before Relieves acceptance.
Provider rejection, SLA failure, production defects, and delivery issues must
have clear financial consequences before payout automation exists.

**Current product-design assumption:** Provider payout, invoicing, and SLA
consequences are manual/business processes for MVP unless explicitly approved
for automation.

**Implementation guardrail:** Do not automate provider payouts, invoice
generation, SLA penalties, or compensation logic until legal/accounting policy
is documented.

### 3. Cancellation, Refund, and Warranty Policy

**Question:** What cancellation, refund, and warranty terms must be shown to the
customer before payment?

**Needs legal/business answer:** Yes.

**Why this matters:** Path A requires the customer to pay before production.
Customer cancellation after payment is a request, not an automatic cancellation,
so the policy must be clear and enforceable.

**Current product-design assumption:** Paid orders are not automatically
cancellable by customer request. Approval depends on order status and the
Relieves/PlacamIA policy.

**Implementation guardrail:** Do not launch real checkout without customer-
visible cancellation/refund terms reviewed by the appropriate advisors.

### 4. Compliance Recommendation Liability

**Question:** What claims may PlacamIA safely make when suggesting signage for a
business context, regulator, or inspection scenario?

**Needs legal/business answer:** Yes.

**Why this matters:** Provider expertise and regulation-derived rules may help
customers, but PlacamIA should not imply guaranteed inspection success or legal
compliance unless that risk is explicitly accepted and reviewed.

**Current product-design assumption:** Use cautious language such as "suggested
based on the information provided" or "commonly requested for this context."
Avoid "guaranteed compliance" and avoid presenting recommendations as legal
advice.

**Implementation guardrail:** Do not implement authoritative automated
compliance claims until legal/compliance review defines allowed language,
disclaimers, and review cadence.

## Related Research

- `docs/research/provider-domain-analysis.md`
- `docs/research/provider-integration-options.md`
- `docs/research/provider-partner-question-log.md`
