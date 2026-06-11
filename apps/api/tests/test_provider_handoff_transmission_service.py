from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.domain.provider_adapter import (
    HandoffResult,
    HandoffState,
    LocalMockProviderAdapter,
    PaidOrderHandoffRequest,
)
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.repositories.order_repository import OrderRepository
from app.services.provider_handoff_payload_service import ProviderHandoffPayloadService
from app.services.provider_handoff_transmission_service import (
    ProviderHandoffTransmissionRejected,
    ProviderHandoffTransmissionService,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for handoff tests."""
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


def seed_product(db) -> Product:
    """Persist one product used as a provider handoff item target."""
    category = Category(name="Emergency", description=None)
    product = Product(
        name="Emergency exit sign",
        description="Current catalog description",
        category=category,
        base_price=Decimal("20.00"),
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def seed_handoff_order(
    db,
    product: Product,
    *,
    status: OrderStatus = OrderStatus.CONFIRMED,
    payment_verified_at: datetime | None = datetime(2026, 6, 9, tzinfo=UTC),
    assigned_provider_id: str | None = "local-provider",
) -> Order:
    """Persist one order candidate with immutable provider payload snapshots."""
    order = Order(
        customer_id=1,
        status=status.value,
        subtotal_amount=Decimal("40.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("40.00"),
        currency="COP",
        payment_provider_reference="pay_internal_ref",
        payment_verified_at=payment_verified_at,
        assigned_provider_id=assigned_provider_id,
        provider_handoff_reference=None,
        provider_handoff_sent_at=None,
        terms_policy_version="terms-v1",
    )
    order.items = [
        OrderItem(
            item_type="product",
            product_id=product.id,
            display_name="Snapshot product name",
            customer_safe_description="Snapshot description",
            selected_options={"material": "acrylic", "size": "20x30"},
            quantity=2,
            unit_price_amount=Decimal("20.00"),
            line_subtotal_amount=Decimal("40.00"),
            line_discount_amount=Decimal("0.00"),
            line_tax_amount=Decimal("0.00"),
            line_total_amount=Decimal("40.00"),
            currency="COP",
            assigned_provider_id="local-provider",
            provider_pricing_reference="local-quote-product-1",
            provider_payload_snapshot={
                "item_type": "product",
                "product_id": product.id,
                "display_name": "Snapshot product name",
                "selected_options": {"material": "acrylic", "size": "20x30"},
                "quantity": 2,
                "payment_provider_reference": "pay_should_not_leave_backend",
                "provider_cost": "12.00",
                "frontend_provider_id": "forged-provider",
            },
        )
    ]
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def transmission_service(db, provider_adapter):
    """Build the provider handoff transmission service under test."""
    return ProviderHandoffTransmissionService(
        OrderRepository(db),
        ProviderHandoffPayloadService(),
        provider_adapter,
    )


class RecordingAdapter:
    """Provider adapter test double that records handoff requests."""

    def __init__(self, state: HandoffState, reason_code: str | None = None) -> None:
        """Store the handoff result returned by the double."""
        self.state = state
        self.reason_code = reason_code
        self.requests: list[PaidOrderHandoffRequest] = []

    def handoff_paid_order(self, request: PaidOrderHandoffRequest) -> HandoffResult:
        """Record the request and return the configured handoff result."""
        self.requests.append(request)
        return HandoffResult(
            provider_reference=f"local-order-{request.order_id}",
            state=self.state,
            idempotency_key=request.idempotency_key,
            reason_code=self.reason_code,
        )


class SequencedPayloadService:
    """Payload service test double that records sequencing."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event log used by the test."""
        self.events = events

    def prepare_handoff_request(
        self,
        order: Order,
        payment_status: PaymentStatus,
    ) -> PaidOrderHandoffRequest:
        """Record payload preparation and return a minimal valid request."""
        self.events.append("payload_prepared")
        return PaidOrderHandoffRequest(
            order_id=order.id,
            assigned_provider_id="local-provider",
            idempotency_key=f"order:{order.id}:provider:local-provider",
            payload={
                "eligibility": {
                    "payment_status": payment_status.value,
                    "order_status": order.status,
                }
            },
        )


class SequencedAdapter(RecordingAdapter):
    """Provider adapter test double that records call order."""

    def __init__(self, events: list[str]) -> None:
        """Store the shared event log used by the test."""
        super().__init__(HandoffState.SENT)
        self.events = events

    def handoff_paid_order(self, request: PaidOrderHandoffRequest) -> HandoffResult:
        """Record adapter transmission after payload preparation."""
        self.events.append("adapter_called")
        return super().handoff_paid_order(request)


def assert_transmission_rejection(exc_info, code: str) -> None:
    """Assert transmission rejection uses the expected stable code."""
    assert exc_info.value.code == code


def test_successful_paid_order_handoff_through_local_adapter():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        original_payment_verified_at = order.payment_verified_at
        adapter = LocalMockProviderAdapter()
        service = transmission_service(db, adapter)

        result = service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.SENT_TO_PROVIDER.value
        assert stored_order.provider_handoff_reference == f"local-order-{order.id}"
        assert stored_order.provider_handoff_sent_at is not None
        assert stored_order.payment_verified_at == original_payment_verified_at
        assert result.provider_reference == f"local-order-{order.id}"
        assert result.idempotency_key == f"order:{order.id}:provider:local-provider"
        assert len(adapter.handoffs_by_key) == 1
    finally:
        db.close()


def test_handoff_can_use_consistent_backend_order_item_provider_assignment():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product, assigned_provider_id=None)
        adapter = LocalMockProviderAdapter()
        service = transmission_service(db, adapter)

        result = service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.SENT_TO_PROVIDER.value
        assert stored_order.provider_handoff_reference == f"local-order-{order.id}"
        assert result.idempotency_key == f"order:{order.id}:provider:local-provider"
        assert len(adapter.handoffs_by_key) == 1
    finally:
        db.close()


def test_handoff_blocked_before_verified_payment_without_adapter_call():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = RecordingAdapter(HandoffState.SENT)
        service = transmission_service(db, adapter)

        with pytest.raises(ProviderHandoffTransmissionRejected) as exc_info:
            service.transmit_paid_order(order, PaymentStatus.FAILED)

        assert_transmission_rejection(exc_info, "payment_not_verified")
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.provider_handoff_reference is None
        assert stored_order.provider_handoff_sent_at is None
        assert adapter.requests == []
    finally:
        db.close()


def test_handoff_blocked_when_order_is_not_confirmed_without_adapter_call():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product, status=OrderStatus.DRAFT)
        adapter = RecordingAdapter(HandoffState.SENT)
        service = transmission_service(db, adapter)

        with pytest.raises(ProviderHandoffTransmissionRejected) as exc_info:
            service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        assert_transmission_rejection(exc_info, "order_not_confirmed")
        assert db.get(Order, order.id).status == OrderStatus.DRAFT.value
        assert adapter.requests == []
    finally:
        db.close()


def test_handoff_blocked_when_order_status_is_not_supported():
    db = build_session()
    try:
        order = Order(
            id=1,
            customer_id=1,
            status="awaiting_provider_magic",
            subtotal_amount=Decimal("40.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("40.00"),
            currency="COP",
            payment_verified_at=datetime(2026, 6, 9, tzinfo=UTC),
            assigned_provider_id="local-provider",
            created_at=datetime(2026, 6, 9, tzinfo=UTC),
        )
        adapter = RecordingAdapter(HandoffState.SENT)
        service = transmission_service(db, adapter)

        with pytest.raises(ProviderHandoffTransmissionRejected) as exc_info:
            service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        assert_transmission_rejection(exc_info, "invalid_order_status")
        assert adapter.requests == []
    finally:
        db.close()


def test_handoff_blocked_when_provider_assignment_is_missing():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product, assigned_provider_id=None)
        order.items[0].assigned_provider_id = ""
        db.commit()
        adapter = RecordingAdapter(HandoffState.SENT)
        service = transmission_service(db, adapter)

        with pytest.raises(ProviderHandoffTransmissionRejected) as exc_info:
            service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        assert_transmission_rejection(exc_info, "provider_assignment_required")
        assert db.get(Order, order.id).provider_handoff_reference is None
        assert adapter.requests == []
    finally:
        db.close()


def test_failed_transmission_leaves_order_state_and_handoff_fields_unchanged():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        original_payment_verified_at = order.payment_verified_at
        adapter = RecordingAdapter(HandoffState.FAILED, reason_code="provider_timeout")
        service = transmission_service(db, adapter)

        with pytest.raises(ProviderHandoffTransmissionRejected) as exc_info:
            service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        assert_transmission_rejection(exc_info, "provider_handoff_failed")
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.provider_handoff_reference is None
        assert stored_order.provider_handoff_sent_at is None
        assert stored_order.payment_verified_at == original_payment_verified_at
        assert len(adapter.requests) == 1
    finally:
        db.close()


def test_payload_preparation_happens_immediately_before_adapter_handoff():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        events: list[str] = []
        adapter = SequencedAdapter(events)
        service = ProviderHandoffTransmissionService(
            OrderRepository(db),
            SequencedPayloadService(events),
            adapter,
        )

        service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        assert events == ["payload_prepared", "adapter_called"]
        assert len(adapter.requests) == 1
    finally:
        db.close()


def test_retry_uses_stable_idempotency_key_after_failed_transmission():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = RecordingAdapter(HandoffState.FAILED, reason_code="provider_timeout")
        service = transmission_service(db, adapter)

        for _ in range(2):
            with pytest.raises(ProviderHandoffTransmissionRejected):
                service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        assert [request.idempotency_key for request in adapter.requests] == [
            f"order:{order.id}:provider:local-provider",
            f"order:{order.id}:provider:local-provider",
        ]
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
    finally:
        db.close()


def test_repeated_successful_transmission_does_not_duplicate_local_provider_order():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = LocalMockProviderAdapter()
        service = transmission_service(db, adapter)

        service.transmit_paid_order(order, PaymentStatus.VERIFIED)
        with pytest.raises(ProviderHandoffTransmissionRejected) as exc_info:
            service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        assert_transmission_rejection(exc_info, "order_not_confirmed")
        assert len(adapter.handoffs_by_key) == 1
    finally:
        db.close()


def test_provider_acceptance_or_rejection_response_does_not_mutate_payment_fields():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        original_payment_verified_at = order.payment_verified_at
        adapter = RecordingAdapter(HandoffState.REJECTED, reason_code="not_accepted")
        service = transmission_service(db, adapter)

        with pytest.raises(ProviderHandoffTransmissionRejected):
            service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.payment_verified_at == original_payment_verified_at
        assert stored_order.provider_handoff_reference is None
    finally:
        db.close()


def test_transmission_logs_exclude_sensitive_customer_and_payment_data(caplog):
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = LocalMockProviderAdapter()
        service = transmission_service(db, adapter)

        with caplog.at_level("INFO"):
            service.transmit_paid_order(order, PaymentStatus.VERIFIED)

        log_text = caplog.text
        assert "provider_handoff_sent" in log_text
        assert "pay_internal_ref" not in log_text
        assert "payment_verified_at" not in log_text
        assert "buyer@example.com" not in log_text
        assert "pay_should_not_leave_backend" not in log_text
    finally:
        db.close()
