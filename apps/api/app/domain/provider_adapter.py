from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class CatalogItemType(StrEnum):
    """Catalog item categories supported by provider adapter requests."""

    PRODUCT = "product"
    KIT = "kit"
    DESIGN = "design"


class AvailabilityState(StrEnum):
    """Provider availability states used by direct-checkout eligibility."""

    AVAILABLE = "available"
    MADE_TO_ORDER_PARAMETRIZABLE = "made_to_order_parametrizable"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    MANUAL_QUOTE_REQUIRED = "manual_quote_required"
    OUTSOURCED_NOT_MVP_DIRECT = "outsourced_not_mvp_direct"
    UNSUPPORTED = "unsupported"


class EligibilityState(StrEnum):
    """Direct-checkout eligibility outcome returned by provider adapters."""

    ELIGIBLE = "eligible"
    NOT_ELIGIBLE = "not_eligible"


class HandoffState(StrEnum):
    """Paid-order handoff states exposed by provider adapters."""

    NOT_SENT = "not_sent"
    SENT = "sent"
    FAILED = "failed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class AcceptanceDecision(StrEnum):
    """Provider acceptance decision for a handed-off paid order."""

    ACCEPT = "accept"
    REJECT = "reject"


class ProviderOrderState(StrEnum):
    """Customer-safe provider fulfillment states mapped into order tracking."""

    SENT_TO_PROVIDER = "sent_to_provider"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IN_PRODUCTION = "in_production"
    READY_FOR_PICKUP = "ready_for_pickup"
    SHIPPED = "shipped"
    DELIVERED = "delivered"


LOCAL_DIRECT_CHECKOUT_ELIGIBLE_STATES = frozenset(
    {
        AvailabilityState.AVAILABLE,
        AvailabilityState.MADE_TO_ORDER_PARAMETRIZABLE,
    }
)
"""Local/mock availability states that may continue through direct checkout."""


@dataclass(frozen=True)
class ProviderItemRequest:
    """Backend-validated catalog item request sent through the adapter boundary.

    Attributes:
        item_type: Type of catalog item being checked.
        item_id: Backend identifier for the product, kit, or design.
        quantity: Requested quantity.
        assigned_provider_id: Backend-selected provider identifier.
        options: Backend-validated material, size, finish, and customization
            options. Frontend-provided provider claims must not be copied here.
    """

    item_type: CatalogItemType
    item_id: int
    quantity: int
    assigned_provider_id: str
    options: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class AvailabilityResult:
    """Availability response from the provider adapter boundary."""

    state: AvailabilityState
    reason_code: str | None = None
    effective_on: date | None = None


@dataclass(frozen=True)
class ProviderPricingResult:
    """Provider-owned cost/capability input for backend pricing.

    This is not a customer price. PlacamIA pricing services must still compute
    final customer price, margin, taxes/fees, discounts, and checkout total.
    """

    provider_cost: Decimal | None
    supports_requested_configuration: bool
    reason_code: str | None = None
    quote_reference: str | None = None
    adjustments: dict[str, Decimal] = field(default_factory=dict)


@dataclass(frozen=True)
class EligibilityResult:
    """Direct-checkout eligibility response returned by the adapter boundary."""

    state: EligibilityState
    assigned_provider_id: str
    reason_code: str | None = None


@dataclass(frozen=True)
class LeadTimeResult:
    """Customer-safe lead time estimate returned by the adapter boundary."""

    production_days: int | None
    dispatch_days: int | None = None
    uncertainty_reason: str | None = None


@dataclass(frozen=True)
class PaidOrderHandoffRequest:
    """Persisted paid-order data prepared for provider handoff.

    Attributes:
        order_id: Persisted PlacamIA order identifier.
        assigned_provider_id: Backend-selected provider identifier.
        idempotency_key: Stable retry key used to avoid duplicate provider
            orders.
        payload: Persisted order, item, design, and delivery data needed for
            fulfillment.
    """

    order_id: int
    assigned_provider_id: str
    idempotency_key: str
    payload: dict[str, object]


@dataclass(frozen=True)
class HandoffResult:
    """Paid-order handoff result returned by the adapter boundary."""

    provider_reference: str
    state: HandoffState
    idempotency_key: str
    reason_code: str | None = None


@dataclass(frozen=True)
class ProviderStatusResult:
    """Provider-side status mapped into a customer-safe order status."""

    provider_reference: str
    provider_status: ProviderOrderState
    customer_safe_status: ProviderOrderState
    synchronized_at: datetime | None = None
    reason_code: str | None = None


@dataclass(frozen=True)
class AcceptanceResult:
    """Provider acceptance/rejection result for a handed-off paid order."""

    provider_reference: str
    accepted: bool
    customer_safe_status: ProviderOrderState
    reason_code: str | None = None


@dataclass(frozen=True)
class LocalProviderFixture:
    """Deterministic local adapter fixture for one backend-owned catalog item.

    Attributes:
        availability_state: Provider availability state returned for the item.
        provider_cost: Provider-owned cost input. This is never a customer
            price or checkout total.
        supports_requested_configuration: Whether the provider can fulfill the
            backend-validated item/options represented by this fixture.
        production_days: Deterministic production lead-time estimate.
        dispatch_days: Deterministic dispatch/pickup lead-time estimate.
        reason_code: Stable machine-readable reason for unavailable or
            unsupported fixture states.
        effective_on: Optional effective date for the fixture's availability
            state.
        adjustments: Provider-owned cost adjustments for backend pricing tests.
            These are not frontend/customer-facing prices.
    """

    availability_state: AvailabilityState = AvailabilityState.AVAILABLE
    provider_cost: Decimal | None = Decimal("0.00")
    supports_requested_configuration: bool = True
    production_days: int | None = 5
    dispatch_days: int | None = 1
    reason_code: str | None = None
    effective_on: date | None = None
    adjustments: dict[str, Decimal] = field(default_factory=dict)


class ProviderAdapter(Protocol):
    """Provider adapter operations used by PlacamIA core services."""

    def check_availability(
        self,
        request: ProviderItemRequest,
    ) -> AvailabilityResult:
        """Return current provider availability for a backend-validated item."""

    def quote_pricing(
        self,
        request: ProviderItemRequest,
    ) -> ProviderPricingResult:
        """Return provider cost/capability input, not customer price."""

    def check_direct_checkout_eligibility(
        self,
        request: ProviderItemRequest,
    ) -> EligibilityResult:
        """Return whether the item can continue through direct checkout."""

    def estimate_lead_time(
        self,
        request: ProviderItemRequest,
    ) -> LeadTimeResult:
        """Return a customer-safe lead time estimate."""

    def handoff_paid_order(
        self,
        request: PaidOrderHandoffRequest,
    ) -> HandoffResult:
        """Send a verified paid order through the provider boundary."""

    def get_handoff_status(
        self,
        provider_reference: str,
    ) -> ProviderStatusResult:
        """Return the mapped provider status for a prior handoff."""

    def record_acceptance(
        self,
        provider_reference: str,
        decision: AcceptanceDecision,
    ) -> AcceptanceResult:
        """Record provider acceptance or rejection for a prior handoff."""


class LocalMockProviderAdapter:
    """Deterministic in-process provider adapter for MVP backend development.

    The adapter performs no network calls and stores handoff state in memory so
    tests can exercise provider-boundary behavior before a real provider
    integration exists.
    """

    def __init__(
        self,
        fixtures: dict[tuple[CatalogItemType, int], LocalProviderFixture] | None = None,
    ) -> None:
        """Initialize local fixtures and in-memory handoff state.

        Args:
            fixtures: Optional item fixture map keyed by item type and item id.
        """
        self.fixtures = dict(fixtures or {})
        self.handoffs_by_key: dict[str, HandoffResult] = {}
        self.status_by_reference: dict[str, ProviderOrderState] = {}

    def check_availability(
        self,
        request: ProviderItemRequest,
    ) -> AvailabilityResult:
        """Return deterministic fixture availability for the requested item."""
        fixture = self._fixture_for(request)
        return AvailabilityResult(
            state=fixture.availability_state,
            reason_code=fixture.reason_code,
            effective_on=fixture.effective_on,
        )

    def quote_pricing(
        self,
        request: ProviderItemRequest,
    ) -> ProviderPricingResult:
        """Return provider cost input without calculating customer price."""
        fixture = self._fixture_for(request)
        return ProviderPricingResult(
            provider_cost=fixture.provider_cost,
            supports_requested_configuration=fixture.supports_requested_configuration,
            reason_code=fixture.reason_code,
            quote_reference=f"local-quote-{request.item_type}-{request.item_id}",
            adjustments=dict(fixture.adjustments),
        )

    def check_direct_checkout_eligibility(
        self,
        request: ProviderItemRequest,
    ) -> EligibilityResult:
        """Return direct-checkout eligibility from fixture availability/capability."""
        fixture = self._fixture_for(request)
        if (
            fixture.availability_state in LOCAL_DIRECT_CHECKOUT_ELIGIBLE_STATES
            and fixture.supports_requested_configuration
            and fixture.provider_cost is not None
        ):
            return EligibilityResult(
                state=EligibilityState.ELIGIBLE,
                assigned_provider_id=request.assigned_provider_id,
            )

        return EligibilityResult(
            state=EligibilityState.NOT_ELIGIBLE,
            assigned_provider_id=request.assigned_provider_id,
            reason_code=fixture.reason_code or fixture.availability_state.value,
        )

    def estimate_lead_time(
        self,
        request: ProviderItemRequest,
    ) -> LeadTimeResult:
        """Return deterministic fixture lead time for the requested item."""
        fixture = self._fixture_for(request)
        return LeadTimeResult(
            production_days=fixture.production_days,
            dispatch_days=fixture.dispatch_days,
            uncertainty_reason=fixture.reason_code,
        )

    def handoff_paid_order(
        self,
        request: PaidOrderHandoffRequest,
    ) -> HandoffResult:
        """Record a paid-order handoff idempotently using the local fixture store."""
        eligibility = request.payload.get("eligibility")
        if (
            not isinstance(eligibility, dict)
            or eligibility.get("payment_status") != "verified"
        ):
            return HandoffResult(
                provider_reference=f"local-order-{request.order_id}",
                state=HandoffState.FAILED,
                idempotency_key=request.idempotency_key,
                reason_code="payment_not_verified",
            )

        existing_handoff = self.handoffs_by_key.get(request.idempotency_key)
        if existing_handoff is not None:
            return existing_handoff

        result = HandoffResult(
            provider_reference=f"local-order-{request.order_id}",
            state=HandoffState.SENT,
            idempotency_key=request.idempotency_key,
        )
        self.handoffs_by_key[request.idempotency_key] = result
        self.status_by_reference[result.provider_reference] = (
            ProviderOrderState.SENT_TO_PROVIDER
        )
        return result

    def get_handoff_status(
        self,
        provider_reference: str,
    ) -> ProviderStatusResult:
        """Return current local handoff status for a provider reference."""
        provider_status = self.status_by_reference.get(
            provider_reference,
            ProviderOrderState.SENT_TO_PROVIDER,
        )
        return ProviderStatusResult(
            provider_reference=provider_reference,
            provider_status=provider_status,
            customer_safe_status=provider_status,
        )

    def record_acceptance(
        self,
        provider_reference: str,
        decision: AcceptanceDecision,
    ) -> AcceptanceResult:
        """Record local provider acceptance or rejection for a handoff."""
        accepted = decision is AcceptanceDecision.ACCEPT
        status = (
            ProviderOrderState.ACCEPTED if accepted else ProviderOrderState.REJECTED
        )
        self.status_by_reference[provider_reference] = status
        return AcceptanceResult(
            provider_reference=provider_reference,
            accepted=accepted,
            customer_safe_status=status,
            reason_code=None if accepted else "provider_rejected",
        )

    def _fixture_for(self, request: ProviderItemRequest) -> LocalProviderFixture:
        """Return a fixture for the request, failing closed when none exists."""
        return self.fixtures.get(
            (request.item_type, request.item_id),
            LocalProviderFixture(
                availability_state=AvailabilityState.UNSUPPORTED,
                provider_cost=None,
                supports_requested_configuration=False,
                reason_code="missing_local_provider_fixture",
            ),
        )
