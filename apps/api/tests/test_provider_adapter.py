from datetime import UTC, datetime
from decimal import Decimal

from app.domain.provider_adapter import (
    AcceptanceDecision,
    AvailabilityState,
    CatalogItemType,
    EligibilityState,
    HandoffState,
    LocalMockProviderAdapter,
    LocalProviderFixture,
    PaidOrderHandoffRequest,
    ProviderItemRequest,
    ProviderOrderState,
)


def build_product_request(product_id: int = 1) -> ProviderItemRequest:
    return ProviderItemRequest(
        item_type=CatalogItemType.PRODUCT,
        item_id=product_id,
        quantity=2,
        assigned_provider_id="local-provider",
        options={"material": "acrylic", "size": "20x30"},
    )


def test_local_adapter_returns_available_item_signals():
    adapter = LocalMockProviderAdapter(
        {
            (CatalogItemType.PRODUCT, 1): LocalProviderFixture(
                availability_state=AvailabilityState.AVAILABLE,
                provider_cost=Decimal("12.50"),
                production_days=3,
                dispatch_days=1,
            )
        }
    )

    request = build_product_request()

    availability = adapter.check_availability(request)
    pricing = adapter.quote_pricing(request)
    eligibility = adapter.check_direct_checkout_eligibility(request)
    lead_time = adapter.estimate_lead_time(request)

    assert availability.state is AvailabilityState.AVAILABLE
    assert pricing.provider_cost == Decimal("12.50")
    assert pricing.supports_requested_configuration is True
    assert pricing.quote_reference == "local-quote-product-1"
    assert eligibility.state is EligibilityState.ELIGIBLE
    assert eligibility.assigned_provider_id == "local-provider"
    assert lead_time.production_days == 3
    assert lead_time.dispatch_days == 1


def test_local_adapter_rejects_manual_quote_item_for_direct_checkout():
    adapter = LocalMockProviderAdapter(
        {
            (CatalogItemType.PRODUCT, 2): LocalProviderFixture(
                availability_state=AvailabilityState.MANUAL_QUOTE_REQUIRED,
                provider_cost=None,
                supports_requested_configuration=False,
                reason_code="manual_quote_required",
            )
        }
    )

    eligibility = adapter.check_direct_checkout_eligibility(build_product_request(2))
    pricing = adapter.quote_pricing(build_product_request(2))

    assert eligibility.state is EligibilityState.NOT_ELIGIBLE
    assert eligibility.reason_code == "manual_quote_required"
    assert pricing.provider_cost is None
    assert pricing.supports_requested_configuration is False


def test_local_adapter_does_not_turn_provider_cost_into_customer_price():
    adapter = LocalMockProviderAdapter(
        {
            (CatalogItemType.PRODUCT, 1): LocalProviderFixture(
                provider_cost=Decimal("9.75"),
            )
        }
    )

    pricing = adapter.quote_pricing(build_product_request())

    assert pricing.provider_cost == Decimal("9.75")
    assert not hasattr(pricing, "customer_price")
    assert not hasattr(pricing, "checkout_total")


def test_local_adapter_requires_verified_payment_before_handoff():
    adapter = LocalMockProviderAdapter()
    request = PaidOrderHandoffRequest(
        order_id=10,
        assigned_provider_id="local-provider",
        idempotency_key="order-10",
        payload={"order_id": 10},
        payment_verified_at=None,
    )

    result = adapter.handoff_paid_order(request)

    assert result.state is HandoffState.FAILED
    assert result.reason_code == "payment_not_verified"


def test_local_adapter_handoff_is_idempotent_by_key():
    adapter = LocalMockProviderAdapter()
    request = PaidOrderHandoffRequest(
        order_id=10,
        assigned_provider_id="local-provider",
        idempotency_key="order-10",
        payload={"order_id": 10},
        payment_verified_at=datetime(2026, 6, 3, tzinfo=UTC),
    )

    first_result = adapter.handoff_paid_order(request)
    second_result = adapter.handoff_paid_order(request)

    assert first_result is second_result
    assert first_result.state is HandoffState.SENT
    assert first_result.provider_reference == "local-order-10"


def test_local_adapter_records_acceptance_and_rejection_statuses():
    adapter = LocalMockProviderAdapter()

    accepted = adapter.record_acceptance(
        provider_reference="local-order-10",
        decision=AcceptanceDecision.ACCEPT,
    )
    accepted_status = adapter.get_handoff_status("local-order-10")

    rejected = adapter.record_acceptance(
        provider_reference="local-order-11",
        decision=AcceptanceDecision.REJECT,
    )
    rejected_status = adapter.get_handoff_status("local-order-11")

    assert accepted.accepted is True
    assert accepted.customer_safe_status is ProviderOrderState.ACCEPTED
    assert accepted_status.customer_safe_status is ProviderOrderState.ACCEPTED
    assert rejected.accepted is False
    assert rejected.reason_code == "provider_rejected"
    assert rejected_status.customer_safe_status is ProviderOrderState.REJECTED
