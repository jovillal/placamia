from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.services.provider_handoff_payload_service import (
    ProviderHandoffPayloadRejected,
    ProviderHandoffPayloadService,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for handoff payload tests."""
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


def seed_product(db, *, name: str = "Current catalog name") -> Product:
    """Persist one product used as mutable catalog traceability."""
    category = Category(name="Emergency", description=None)
    product = Product(
        name=name,
        description="Current catalog description",
        category=category,
        base_price=Decimal("20.00"),
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def seed_confirmed_order(
    db,
    product: Product,
    *,
    status: OrderStatus = OrderStatus.CONFIRMED,
    assigned_provider_id: str | None = "local-provider",
    provider_payload_snapshot: dict | None = None,
) -> Order:
    """Persist one paid-order candidate with immutable item snapshots."""
    snapshot = (
        provider_payload_snapshot
        if provider_payload_snapshot is not None
        else {
            "item_type": "product",
            "product_id": product.id,
            "display_name": "Snapshot product name",
            "selected_options": {"material": "acrylic", "size": "20x30"},
            "quantity": 2,
            "provider_quote_reference": "raw-provider-quote",
            "provider_cost": "12.00",
            "frontend_provider_id": "forged-provider",
            "nested": {
                "payment_provider_reference": "pay_should_not_leave_backend",
                "manufacturing_note": "Use rounded corners",
            },
        }
    )
    order = Order(
        customer_id=1,
        status=status.value,
        subtotal_amount=Decimal("40.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("40.00"),
        currency="COP",
        payment_provider_reference="pay_internal_ref",
        payment_verified_at=datetime(2026, 6, 9, tzinfo=UTC),
        assigned_provider_id=assigned_provider_id,
        provider_handoff_reference=None,
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
            provider_payload_snapshot=snapshot,
        )
    ]
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def assert_rejection(exc_info, code: str) -> None:
    """Assert a handoff payload rejection uses a stable reason code."""
    assert exc_info.value.code == code


def test_prepare_handoff_payload_from_persisted_order_snapshots():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_confirmed_order(db, product)
        service = ProviderHandoffPayloadService()

        request = service.prepare_handoff_request(
            order,
            PaymentStatus.VERIFIED,
            handoff_attempt_id="attempt-123",
        )

        assert request.order_id == order.id
        assert request.assigned_provider_id == "local-provider"
        assert request.idempotency_key == f"order:{order.id}:provider:local-provider"
        assert request.payment_verified_at == order.payment_verified_at
        payload = request.payload
        assert payload["contract_version"] == "paid_order_handoff_v1"
        assert payload["correlation"] == {
            "order_id": order.id,
            "assigned_provider_id": "local-provider",
            "handoff_attempt_id": "attempt-123",
            "idempotency_key": f"order:{order.id}:provider:local-provider",
        }
        assert payload["eligibility"] == {
            "payment_status": "verified",
            "order_status": "confirmed",
        }
        assert payload["provider_assignment"] == {
            "assigned_provider_id": "local-provider"
        }
        assert payload["order"] == {
            "id": order.id,
            "created_at": order.created_at.isoformat(),
        }
        assert len(payload["items"]) == 1
        item_payload = payload["items"][0]
        assert item_payload["order_item_id"] == order.items[0].id
        assert item_payload["display_name"] == "Snapshot product name"
        assert item_payload["customer_safe_description"] == "Snapshot description"
        assert item_payload["selected_options"] == {
            "material": "acrylic",
            "size": "20x30",
        }
        assert item_payload["provider_payload_snapshot"] == {
            "item_type": "product",
            "product_id": product.id,
            "display_name": "Snapshot product name",
            "selected_options": {"material": "acrylic", "size": "20x30"},
            "quantity": 2,
            "nested": {"manufacturing_note": "Use rounded corners"},
        }
        assert payload["delivery"]["status"] == "deferred"
        assert "address" in payload["delivery"]["deferred_fields"]
        assert payload["shipment"]["qr_reference"] is None
        assert payload["shipment"]["carrier_reference"] is None
    finally:
        db.close()


def test_payload_excludes_sensitive_payment_pricing_and_frontend_fields():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_confirmed_order(db, product)
        service = ProviderHandoffPayloadService()

        payload = service.prepare_handoff_request(
            order,
            PaymentStatus.VERIFIED,
            handoff_attempt_id="attempt-123",
        ).payload
        payload_text = str(payload)

        assert "pay_internal_ref" not in payload_text
        assert "payment_verified_at" not in payload_text
        assert "raw-provider-quote" not in payload_text
        assert "provider_quote_reference" not in payload_text
        assert "provider_cost" not in payload_text
        assert "forged-provider" not in payload_text
        assert "frontend_provider_id" not in payload_text
        assert "line_total_amount" not in payload_text
        assert "unit_price_amount" not in payload_text
        assert "terms_policy_version" not in payload_text
    finally:
        db.close()


def test_unverified_payment_rejects_payload_preparation_without_mutation():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_confirmed_order(db, product)
        service = ProviderHandoffPayloadService()

        with pytest.raises(ProviderHandoffPayloadRejected) as exc_info:
            service.prepare_handoff_request(order, PaymentStatus.PENDING)

        assert_rejection(exc_info, "payment_not_verified")
        assert order.status == OrderStatus.CONFIRMED.value
        assert order.provider_handoff_reference is None
    finally:
        db.close()


def test_non_confirmed_order_rejects_payload_preparation_without_mutation():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_confirmed_order(db, product, status=OrderStatus.DRAFT)
        service = ProviderHandoffPayloadService()

        with pytest.raises(ProviderHandoffPayloadRejected) as exc_info:
            service.prepare_handoff_request(order, PaymentStatus.VERIFIED)

        assert_rejection(exc_info, "order_not_confirmed")
        assert order.status == OrderStatus.DRAFT.value
        assert order.provider_handoff_reference is None
    finally:
        db.close()


def test_missing_payment_verification_timestamp_rejects_payload_preparation():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_confirmed_order(db, product)
        order.payment_verified_at = None
        db.commit()
        service = ProviderHandoffPayloadService()

        with pytest.raises(ProviderHandoffPayloadRejected) as exc_info:
            service.prepare_handoff_request(order, PaymentStatus.VERIFIED)

        assert_rejection(exc_info, "payment_verification_timestamp_required")
        assert order.status == OrderStatus.CONFIRMED.value
        assert order.provider_handoff_reference is None
    finally:
        db.close()


def test_missing_provider_assignment_rejects_payload_preparation():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_confirmed_order(db, product, assigned_provider_id=None)
        order.items[0].assigned_provider_id = ""
        db.commit()
        service = ProviderHandoffPayloadService()

        with pytest.raises(ProviderHandoffPayloadRejected) as exc_info:
            service.prepare_handoff_request(order, PaymentStatus.VERIFIED)

        assert_rejection(exc_info, "provider_assignment_required")
    finally:
        db.close()


def test_missing_order_items_rejects_payload_preparation():
    order = Order(
        id=1,
        customer_id=1,
        status=OrderStatus.CONFIRMED.value,
        subtotal_amount=Decimal("40.00"),
        total_amount=Decimal("40.00"),
        currency="COP",
        payment_verified_at=datetime(2026, 6, 9, tzinfo=UTC),
        assigned_provider_id="local-provider",
        created_at=datetime(2026, 6, 9, tzinfo=UTC),
    )
    service = ProviderHandoffPayloadService()

    with pytest.raises(ProviderHandoffPayloadRejected) as exc_info:
        service.prepare_handoff_request(order, PaymentStatus.VERIFIED)

    assert_rejection(exc_info, "order_items_required")


def test_missing_provider_payload_snapshot_rejects_payload_preparation():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_confirmed_order(db, product, provider_payload_snapshot={})
        service = ProviderHandoffPayloadService()

        with pytest.raises(ProviderHandoffPayloadRejected) as exc_info:
            service.prepare_handoff_request(order, PaymentStatus.VERIFIED)

        assert_rejection(exc_info, "provider_payload_snapshot_required")
    finally:
        db.close()


def test_frontend_provider_assignment_claims_cannot_influence_payload():
    db = build_session()
    try:
        product = seed_product(db)
        order = seed_confirmed_order(
            db,
            product,
            provider_payload_snapshot={
                "display_name": "Snapshot product name",
                "assigned_provider_id": "forged-provider",
                "provider_assignment": {"assigned_provider_id": "forged-provider"},
                "provider_id": "forged-provider",
                "manufacturing_note": "Use rounded corners",
            },
        )
        service = ProviderHandoffPayloadService()

        payload = service.prepare_handoff_request(
            order,
            PaymentStatus.VERIFIED,
            handoff_attempt_id="attempt-123",
        ).payload

        assert payload["provider_assignment"]["assigned_provider_id"] == (
            "local-provider"
        )
        payload_text = str(payload)
        assert "forged-provider" not in payload_text
        assert payload["items"][0]["provider_payload_snapshot"] == {
            "display_name": "Snapshot product name",
            "manufacturing_note": "Use rounded corners",
        }
    finally:
        db.close()


def test_changed_catalog_data_does_not_alter_snapshot_payload_fields():
    db = build_session()
    try:
        product = seed_product(db, name="Original catalog name")
        order = seed_confirmed_order(db, product)
        product.name = "Changed catalog name"
        product.description = "Changed catalog description"
        db.commit()
        service = ProviderHandoffPayloadService()

        payload = service.prepare_handoff_request(
            order,
            PaymentStatus.VERIFIED,
            handoff_attempt_id="attempt-123",
        ).payload

        assert payload["items"][0]["display_name"] == "Snapshot product name"
        assert payload["items"][0]["customer_safe_description"] == (
            "Snapshot description"
        )
        assert payload["items"][0]["provider_payload_snapshot"]["display_name"] == (
            "Snapshot product name"
        )
        assert order.items[0].product.name == "Changed catalog name"
    finally:
        db.close()
