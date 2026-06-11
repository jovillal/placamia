from datetime import UTC, datetime
from decimal import Decimal

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
from app.services.paid_order_handoff_orchestration_service import (
    PaidOrderHandoffOrchestrationService,
    PaidOrderHandoffOrchestrationState,
)
from app.services.provider_handoff_payload_service import ProviderHandoffPayloadService
from app.services.provider_handoff_transmission_service import (
    ProviderHandoffTransmissionResult,
    ProviderHandoffTransmissionService,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for orchestration tests."""
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
    payment_provider_reference: str | None = "pay_internal_ref",
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
        payment_provider_reference=payment_provider_reference,
        payment_verified_at=payment_verified_at,
        assigned_provider_id="local-provider",
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


def orchestration_service(db, provider_adapter):
    """Build the paid-order handoff orchestration service under test."""
    return PaidOrderHandoffOrchestrationService(
        ProviderHandoffTransmissionService(
            OrderRepository(db),
            ProviderHandoffPayloadService(),
            provider_adapter,
        )
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


class RecordingTransmissionService:
    """Transmission service test double that records orchestration delegation."""

    def __init__(self) -> None:
        """Initialize an empty transmission call log."""
        self.calls: list[tuple[Order, PaymentStatus]] = []

    def transmit_paid_order(
        self,
        order: Order,
        payment_status: PaymentStatus,
    ) -> ProviderHandoffTransmissionResult:
        """Record the delegated transmission call and return a success result."""
        self.calls.append((order, payment_status))
        return ProviderHandoffTransmissionResult(
            order=order,
            provider_reference=f"local-order-{order.id}",
            idempotency_key=f"order:{order.id}:provider:local-provider",
            sent_at=datetime(2026, 6, 9, tzinfo=UTC),
        )


def test_orchestration_delegates_eligible_handoff_to_transmission_service():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        transmission_service = RecordingTransmissionService()
        service = PaidOrderHandoffOrchestrationService(transmission_service)

        result = service.orchestrate_confirmed_paid_order(
            order,
            PaymentStatus.VERIFIED,
        )

        assert result.state is PaidOrderHandoffOrchestrationState.SENT
        assert transmission_service.calls == [(order, PaymentStatus.VERIFIED)]
        assert result.idempotency_key == f"order:{order.id}:provider:local-provider"
    finally:
        db.close()


def test_confirmed_paid_order_triggers_one_provider_handoff_attempt():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = RecordingAdapter(HandoffState.SENT)
        service = orchestration_service(db, adapter)

        result = service.orchestrate_confirmed_paid_order(
            order,
            PaymentStatus.VERIFIED,
        )

        stored_order = db.get(Order, order.id)
        assert result.state is PaidOrderHandoffOrchestrationState.SENT
        assert stored_order.status == OrderStatus.SENT_TO_PROVIDER.value
        assert stored_order.provider_handoff_reference == f"local-order-{order.id}"
        assert stored_order.provider_handoff_sent_at is not None
        assert len(adapter.requests) == 1
    finally:
        db.close()


def test_draft_order_does_not_trigger_provider_handoff():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product, status=OrderStatus.DRAFT)
        adapter = RecordingAdapter(HandoffState.SENT)
        service = orchestration_service(db, adapter)

        result = service.orchestrate_confirmed_paid_order(
            order,
            PaymentStatus.VERIFIED,
        )

        assert result.state is PaidOrderHandoffOrchestrationState.SKIPPED
        assert result.rejection_code == "order_not_confirmed"
        assert db.get(Order, order.id).status == OrderStatus.DRAFT.value
        assert adapter.requests == []
    finally:
        db.close()


def test_unverified_payment_does_not_trigger_provider_handoff():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = RecordingAdapter(HandoffState.SENT)
        service = orchestration_service(db, adapter)

        result = service.orchestrate_confirmed_paid_order(
            order,
            PaymentStatus.FAILED,
        )

        assert result.state is PaidOrderHandoffOrchestrationState.SKIPPED
        assert result.rejection_code == "payment_not_verified"
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
        assert adapter.requests == []
    finally:
        db.close()


def test_unpaid_order_does_not_trigger_provider_handoff():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(
            db,
            product,
            payment_verified_at=None,
            payment_provider_reference=None,
        )
        adapter = RecordingAdapter(HandoffState.SENT)
        service = orchestration_service(db, adapter)

        result = service.orchestrate_confirmed_paid_order(
            order,
            PaymentStatus.VERIFIED,
        )

        assert result.state is PaidOrderHandoffOrchestrationState.SKIPPED
        assert result.rejection_code == "payment_verification_timestamp_required"
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
        assert adapter.requests == []
    finally:
        db.close()


def test_failed_handoff_leaves_confirmed_order_and_payment_fields_for_retry():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        original_verified_at = order.payment_verified_at
        adapter = RecordingAdapter(HandoffState.FAILED, reason_code="provider_timeout")
        service = orchestration_service(db, adapter)

        result = service.orchestrate_confirmed_paid_order(
            order,
            PaymentStatus.VERIFIED,
        )

        stored_order = db.get(Order, order.id)
        assert result.state is PaidOrderHandoffOrchestrationState.FAILED
        assert result.rejection_code == "provider_handoff_failed"
        assert result.reason_code == "provider_timeout"
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.payment_verified_at == original_verified_at
        assert stored_order.provider_handoff_reference is None
        assert stored_order.provider_handoff_sent_at is None
        assert len(adapter.requests) == 1
    finally:
        db.close()


def test_repeated_orchestration_does_not_duplicate_local_provider_order():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = LocalMockProviderAdapter()
        service = orchestration_service(db, adapter)

        first_result = service.orchestrate_confirmed_paid_order(
            order,
            PaymentStatus.VERIFIED,
        )
        second_result = service.orchestrate_confirmed_paid_order(
            order,
            PaymentStatus.VERIFIED,
        )

        assert first_result.state is PaidOrderHandoffOrchestrationState.SENT
        assert second_result.state is PaidOrderHandoffOrchestrationState.SKIPPED
        assert second_result.rejection_code == "order_not_confirmed"
        assert (
            first_result.idempotency_key == f"order:{order.id}:provider:local-provider"
        )
        assert len(adapter.handoffs_by_key) == 1
    finally:
        db.close()


def test_failed_repeated_orchestration_uses_stable_idempotency_key():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = RecordingAdapter(HandoffState.FAILED, reason_code="provider_timeout")
        service = orchestration_service(db, adapter)

        for _ in range(2):
            service.orchestrate_confirmed_paid_order(order, PaymentStatus.VERIFIED)

        assert [request.idempotency_key for request in adapter.requests] == [
            f"order:{order.id}:provider:local-provider",
            f"order:{order.id}:provider:local-provider",
        ]
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
    finally:
        db.close()


def test_orchestration_logs_exclude_sensitive_customer_and_payment_data(caplog):
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_handoff_order(db, product)
        adapter = RecordingAdapter(HandoffState.FAILED, reason_code="provider_timeout")
        service = orchestration_service(db, adapter)

        with caplog.at_level("INFO"):
            service.orchestrate_confirmed_paid_order(order, PaymentStatus.VERIFIED)

        log_text = caplog.text
        assert "provider_handoff_orchestration_failed" in log_text
        assert "pay_internal_ref" not in log_text
        assert "payment_verified_at" not in log_text
        assert "buyer@example.com" not in log_text
        assert "pay_should_not_leave_backend" not in log_text
    finally:
        db.close()
