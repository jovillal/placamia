from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.domain.provider_adapter import (
    AcceptanceDecision,
    AcceptanceResult,
    ProviderOrderState,
)
from app.models import user as _user_models  # noqa: F401
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.services.provider_acceptance_service import (
    ProviderAcceptanceRejected,
    ProviderAcceptanceService,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for provider decisions."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    return testing_session_local()


def seed_order(
    db,
    *,
    status: OrderStatus = OrderStatus.SENT_TO_PROVIDER,
    provider_handoff_reference: str | None = "local-order-1",
) -> Order:
    """Persist one paid order candidate for provider decision tests."""
    order = Order(
        customer_id=1,
        status=status.value,
        subtotal_amount=Decimal("40.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("40.00"),
        currency="COP",
        payment_provider_reference="pay_internal_ref",
        payment_verified_at=datetime(2026, 6, 10, tzinfo=UTC),
        assigned_provider_id="local-provider",
        provider_handoff_reference=provider_handoff_reference,
        provider_handoff_sent_at=datetime(2026, 6, 10, tzinfo=UTC),
        terms_policy_version="terms-v1",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


class RecordingAcceptanceAdapter:
    """Provider adapter test double that records acceptance decisions."""

    def __init__(
        self,
        *,
        provider_reference: str = "local-order-1",
        accepted: bool | None = None,
        customer_safe_status: ProviderOrderState | None = None,
        reason_code: str | None = None,
    ) -> None:
        """Store configurable adapter response fields."""
        self.provider_reference = provider_reference
        self.accepted = accepted
        self.customer_safe_status = customer_safe_status
        self.reason_code = reason_code
        self.calls: list[tuple[str, AcceptanceDecision]] = []

    def record_acceptance(
        self,
        provider_reference: str,
        decision: AcceptanceDecision,
    ) -> AcceptanceResult:
        """Record the adapter call and return the configured result."""
        self.calls.append((provider_reference, decision))
        accepted = self.accepted
        if accepted is None:
            accepted = decision is AcceptanceDecision.ACCEPT
        customer_safe_status = self.customer_safe_status
        if customer_safe_status is None:
            customer_safe_status = (
                ProviderOrderState.ACCEPTED if accepted else ProviderOrderState.REJECTED
            )
        return AcceptanceResult(
            provider_reference=self.provider_reference,
            accepted=accepted,
            customer_safe_status=customer_safe_status,
            reason_code=self.reason_code,
        )


def provider_acceptance_service(db, adapter):
    """Build the provider acceptance service under test."""
    return ProviderAcceptanceService(OrderRepository(db), adapter)


def assert_rejection(exc_info, code: str) -> None:
    """Assert provider decision rejection uses a stable code."""
    assert exc_info.value.code == code


def test_provider_acceptance_moves_sent_order_to_accepted():
    db = build_session()
    try:
        order = seed_order(db)
        original_payment_verified_at = order.payment_verified_at
        adapter = RecordingAcceptanceAdapter()
        service = provider_acceptance_service(db, adapter)

        result = service.process_provider_decision(
            order.id,
            AcceptanceDecision.ACCEPT,
        )

        stored_order = db.get(Order, order.id)
        assert result.order.status == OrderStatus.ACCEPTED.value
        assert result.customer_safe_status is ProviderOrderState.ACCEPTED
        assert result.idempotent is False
        assert stored_order.status == OrderStatus.ACCEPTED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_payment_verified_at
        assert stored_order.provider_handoff_reference == "local-order-1"
        assert adapter.calls == [("local-order-1", AcceptanceDecision.ACCEPT)]
    finally:
        db.close()


def test_provider_rejection_moves_sent_order_to_cancelled_without_payment_rollback():
    db = build_session()
    try:
        order = seed_order(db)
        original_payment_verified_at = order.payment_verified_at
        adapter = RecordingAcceptanceAdapter(reason_code="provider_timeout")
        service = provider_acceptance_service(db, adapter)

        result = service.process_provider_decision(
            order.id,
            AcceptanceDecision.REJECT,
        )

        stored_order = db.get(Order, order.id)
        assert result.order.status == OrderStatus.CANCELLED.value
        assert result.customer_safe_status is ProviderOrderState.REJECTED
        assert result.customer_safe_reason_code == "provider_unable_to_fulfill"
        assert stored_order.status == OrderStatus.CANCELLED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_payment_verified_at
        assert stored_order.provider_handoff_reference == "local-order-1"
        assert adapter.calls == [("local-order-1", AcceptanceDecision.REJECT)]
    finally:
        db.close()


def test_provider_decision_from_invalid_order_state_is_rejected_without_adapter_call():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.CONFIRMED)
        adapter = RecordingAcceptanceAdapter()
        service = provider_acceptance_service(db, adapter)

        with pytest.raises(ProviderAcceptanceRejected) as exc_info:
            service.process_provider_decision(order.id, AcceptanceDecision.ACCEPT)

        assert_rejection(exc_info, "order_not_sent_to_provider")
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert adapter.calls == []
    finally:
        db.close()


def test_provider_decision_requires_persisted_handoff_reference_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, provider_handoff_reference=None)
        adapter = RecordingAcceptanceAdapter()
        service = provider_acceptance_service(db, adapter)

        with pytest.raises(ProviderAcceptanceRejected) as exc_info:
            service.process_provider_decision(order.id, AcceptanceDecision.ACCEPT)

        assert_rejection(exc_info, "provider_handoff_reference_required")
        assert db.get(Order, order.id).status == OrderStatus.SENT_TO_PROVIDER.value
        assert adapter.calls == []
    finally:
        db.close()


def test_reprocessing_acceptance_for_accepted_order_is_idempotent_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.ACCEPTED)
        adapter = RecordingAcceptanceAdapter()
        service = provider_acceptance_service(db, adapter)

        result = service.process_provider_decision(
            order.id,
            AcceptanceDecision.ACCEPT,
        )

        assert result.idempotent is True
        assert result.order.status == OrderStatus.ACCEPTED.value
        assert db.get(Order, order.id).status == OrderStatus.ACCEPTED.value
        assert adapter.calls == []
    finally:
        db.close()


def test_reprocessing_rejection_for_provider_cancelled_order_is_idempotent():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.CANCELLED)
        adapter = RecordingAcceptanceAdapter()
        service = provider_acceptance_service(db, adapter)

        result = service.process_provider_decision(
            order.id,
            AcceptanceDecision.REJECT,
        )

        assert result.idempotent is True
        assert result.order.status == OrderStatus.CANCELLED.value
        assert result.customer_safe_reason_code == "provider_unable_to_fulfill"
        assert adapter.calls == []
    finally:
        db.close()


def test_acceptance_after_provider_rejection_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.CANCELLED)
        adapter = RecordingAcceptanceAdapter()
        service = provider_acceptance_service(db, adapter)

        with pytest.raises(ProviderAcceptanceRejected) as exc_info:
            service.process_provider_decision(order.id, AcceptanceDecision.ACCEPT)

        assert_rejection(exc_info, "provider_decision_conflict")
        assert db.get(Order, order.id).status == OrderStatus.CANCELLED.value
        assert adapter.calls == []
    finally:
        db.close()


def test_rejection_after_provider_acceptance_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db, status=OrderStatus.ACCEPTED)
        adapter = RecordingAcceptanceAdapter()
        service = provider_acceptance_service(db, adapter)

        with pytest.raises(ProviderAcceptanceRejected) as exc_info:
            service.process_provider_decision(order.id, AcceptanceDecision.REJECT)

        assert_rejection(exc_info, "provider_decision_conflict")
        assert db.get(Order, order.id).status == OrderStatus.ACCEPTED.value
        assert adapter.calls == []
    finally:
        db.close()


def test_conflicting_adapter_result_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db)
        adapter = RecordingAcceptanceAdapter(
            accepted=False,
            customer_safe_status=ProviderOrderState.REJECTED,
        )
        service = provider_acceptance_service(db, adapter)

        with pytest.raises(ProviderAcceptanceRejected) as exc_info:
            service.process_provider_decision(order.id, AcceptanceDecision.ACCEPT)

        assert_rejection(exc_info, "provider_acceptance_result_mismatch")
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.SENT_TO_PROVIDER.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert adapter.calls == [("local-order-1", AcceptanceDecision.ACCEPT)]
    finally:
        db.close()


def test_provider_reference_mismatch_is_rejected_without_mutation():
    db = build_session()
    try:
        order = seed_order(db)
        adapter = RecordingAcceptanceAdapter(provider_reference="other-order")
        service = provider_acceptance_service(db, adapter)

        with pytest.raises(ProviderAcceptanceRejected) as exc_info:
            service.process_provider_decision(order.id, AcceptanceDecision.ACCEPT)

        assert_rejection(exc_info, "provider_reference_mismatch")
        assert db.get(Order, order.id).status == OrderStatus.SENT_TO_PROVIDER.value
    finally:
        db.close()
