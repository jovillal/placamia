import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.main import app
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.design import Design
from app.models.kit import Kit
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.template import Template
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.services.order_detail_service import OrderDetailService
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


ORDER_DETAIL_FIELDS = {
    "id",
    "status",
    "currency",
    "subtotal_amount",
    "discount_amount",
    "tax_amount",
    "total_amount",
    "payment_verified_at",
    "provider_handoff_sent_at",
    "created_at",
    "updated_at",
    "items",
}
ORDER_DETAIL_ITEM_FIELDS = {
    "item_type",
    "display_name",
    "customer_safe_description",
    "selected_options",
    "quantity",
    "unit_price_amount",
    "line_subtotal_amount",
    "line_discount_amount",
    "line_tax_amount",
    "line_total_amount",
    "currency",
}


def build_session() -> Session:
    """Build an isolated in-memory database session for Order detail tests."""
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


def seed_user(db: Session, email: str) -> User:
    """Persist one customer used by Order detail tests."""
    user = User(email=email, full_name="Test Buyer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_catalog_references(
    db: Session,
    customer: User,
) -> tuple[Product, Kit, Template, Design]:
    """Persist mutable catalog rows referenced only for Order traceability."""
    product = Product(
        name="Mutable product name",
        description="Mutable product description",
        category=Category(name="Emergency", description=None),
        base_price=Decimal("999.99"),
    )
    kit = Kit(name="Mutable kit name", description="Mutable kit description")
    template = Template(
        name="Mutable template name",
        description="Mutable template description",
        product=product,
    )
    design = Design(
        customer=customer,
        template=template,
        customization_values={"current": "catalog state"},
    )
    db.add_all([product, kit, template, design])
    db.commit()
    for record in (product, kit, template, design):
        db.refresh(record)
    return product, kit, template, design


def build_snapshot_item(
    *,
    item_type: str,
    display_name: str,
    quantity: int,
    product_id: int | None = None,
    kit_id: int | None = None,
    template_id: int | None = None,
    design_id: int | None = None,
) -> OrderItem:
    """Build one persisted customer and provider snapshot row."""
    unit_price = Decimal("20.00")
    line_total = unit_price * quantity
    return OrderItem(
        item_type=item_type,
        product_id=product_id,
        kit_id=kit_id,
        template_id=template_id,
        design_id=design_id,
        display_name=display_name,
        customer_safe_description=f"Purchased {item_type} snapshot.",
        selected_options={"snapshot": item_type},
        quantity=quantity,
        unit_price_amount=unit_price,
        line_subtotal_amount=line_total,
        line_discount_amount=Decimal("0.00"),
        line_tax_amount=Decimal("0.00"),
        line_total_amount=line_total,
        currency="COP",
        assigned_provider_id=f"internal-{item_type}-provider",
        provider_pricing_reference=f"internal-{item_type}-quote",
        provider_payload_snapshot={"internal": f"{item_type}-payload"},
    )


def seed_order(
    db: Session,
    customer: User,
    *,
    status: OrderStatus = OrderStatus.CONFIRMED,
    include_catalog_references: bool = True,
    payment_verified_at: datetime | None = None,
    provider_handoff_sent_at: datetime | None = None,
) -> Order:
    """Persist one Order with immutable Product, Kit, and Design snapshots."""
    product_id = kit_id = template_id = design_id = None
    if include_catalog_references:
        product, kit, template, design = seed_catalog_references(db, customer)
        product_id = product.id
        kit_id = kit.id
        template_id = template.id
        design_id = design.id

    timestamp = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    order = Order(
        customer_id=customer.id,
        status=status.value,
        cancellation_requested_from=(
            OrderStatus.ACCEPTED.value
            if status is OrderStatus.CANCELLATION_REQUESTED
            else None
        ),
        subtotal_amount=Decimal("120.00"),
        discount_amount=Decimal("5.00"),
        tax_amount=Decimal("10.00"),
        total_amount=Decimal("125.00"),
        currency="COP",
        payment_provider_reference="internal-payment-reference",
        payment_verified_at=payment_verified_at,
        assigned_provider_id="internal-order-provider",
        provider_handoff_reference="internal-handoff-reference",
        provider_handoff_sent_at=provider_handoff_sent_at,
        terms_policy_version="internal-policy-v1",
        created_at=timestamp,
        updated_at=timestamp,
    )
    order.items = [
        build_snapshot_item(
            item_type="product",
            display_name="Purchased product snapshot",
            quantity=1,
            product_id=product_id,
        ),
        build_snapshot_item(
            item_type="kit",
            display_name="Purchased kit snapshot",
            quantity=2,
            kit_id=kit_id,
        ),
        build_snapshot_item(
            item_type="design",
            display_name="Purchased design snapshot",
            quantity=3,
            product_id=product_id,
            template_id=template_id,
            design_id=design_id,
        ),
    ]
    order.payments = [
        Payment(
            provider_code="legacy_generic",
            merchant_reference=f"legacy-detail-{order.id}",
            status=PaymentStatus.INITIATED.value,
            amount=order.total_amount,
            currency=order.currency,
            payment_provider_reference="internal-payment-attempt",
        )
    ]
    db.add(order)
    db.commit()
    db.refresh(order)
    db.add(
        AuditLog(
            actor_user_id=customer.id,
            action="test_order_seeded",
            resource_type="order",
            resource_id=str(order.id),
            event_details={"internal": "audit-state"},
        )
    )
    db.commit()
    return order


def configure_order_detail_test(
    db: Session,
    current_user: User | None,
) -> None:
    """Install database and optional authentication dependency overrides."""

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    if current_user is not None:

        async def override_get_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = override_get_current_user


async def request_order_detail(
    order_id: int,
    params: dict[str, object] | None = None,
    *,
    headers: dict[str, str] | None = None,
):
    """Call the customer Order detail endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(
            f"/api/v1/orders/{order_id}",
            params=params,
            headers=headers,
        )


def persistence_snapshot(db: Session) -> dict[str, list[tuple[object, ...]]]:
    """Return security-relevant Order and OrderItem persistence state."""
    return {
        "orders": list(
            db.execute(
                select(
                    Order.id,
                    Order.customer_id,
                    Order.status,
                    Order.cancellation_requested_from,
                    Order.total_amount,
                    Order.payment_provider_reference,
                    Order.payment_verified_at,
                    Order.assigned_provider_id,
                    Order.provider_handoff_reference,
                    Order.provider_handoff_sent_at,
                    Order.terms_policy_version,
                    Order.updated_at,
                ).order_by(Order.id)
            ).all()
        ),
        "items": list(
            db.execute(
                select(
                    OrderItem.id,
                    OrderItem.order_id,
                    OrderItem.display_name,
                    OrderItem.selected_options,
                    OrderItem.line_total_amount,
                    OrderItem.assigned_provider_id,
                    OrderItem.provider_pricing_reference,
                    OrderItem.provider_payload_snapshot,
                ).order_by(OrderItem.id)
            ).all()
        ),
        "payments": list(
            db.execute(
                select(
                    Payment.id,
                    Payment.order_id,
                    Payment.status,
                    Payment.amount,
                    Payment.currency,
                    Payment.payment_provider_reference,
                    Payment.verified_at,
                    Payment.updated_at,
                ).order_by(Payment.id)
            ).all()
        ),
        "audit_logs": list(
            db.execute(
                select(
                    AuditLog.id,
                    AuditLog.actor_user_id,
                    AuditLog.action,
                    AuditLog.resource_type,
                    AuditLog.resource_id,
                    AuditLog.event_details,
                    AuditLog.created_at,
                ).order_by(AuditLog.id)
            ).all()
        ),
    }


def test_order_detail_service_uses_owner_scope_and_sorts_snapshot_rows():
    calls = []
    first = OrderItem(id=1, item_type="product")
    later = OrderItem(id=3, item_type="kit")
    order = Order(id=7, customer_id=11)
    order.items = [later, first]

    class FakeOrderRepository:
        def get_order_detail_for_customer(self, order_id, customer_id):
            calls.append((order_id, customer_id))
            return order

    result = OrderDetailService(FakeOrderRepository()).get_customer_order_detail(
        order_id=7,
        customer_id=11,
    )

    assert result is not None
    assert result.order is order
    assert result.items == (first, later)
    assert calls == [(7, 11)]


def test_order_repository_loads_only_owned_detail_snapshot_columns():
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        other = seed_user(db, "other@example.com")
        order = seed_order(db, owner)
        owner_id = owner.id
        other_id = other.id
        order_id = order.id
        db.expunge_all()

        repository = OrderRepository(db)
        loaded = repository.get_order_detail_for_customer(order_id, owner_id)

        assert loaded is not None
        assert repository.get_order_detail_for_customer(order_id, other_id) is None
        assert repository.get_order_detail_for_customer(999, owner_id) is None
        assert inspect(loaded).unloaded >= {
            "customer",
            "payments",
            "customer_id",
            "payment_provider_reference",
            "assigned_provider_id",
            "provider_handoff_reference",
            "terms_policy_version",
            "cancellation_requested_from",
        }
        assert [item.item_type for item in loaded.items] == [
            "product",
            "kit",
            "design",
        ]
        for item in loaded.items:
            state = inspect(item)
            assert state.unloaded >= {
                "order",
                "product",
                "kit",
                "template",
                "design",
                "order_id",
                "product_id",
                "kit_id",
                "template_id",
                "design_id",
                "assigned_provider_id",
                "provider_pricing_reference",
                "provider_payload_snapshot",
                "created_at",
            }
            with pytest.raises(InvalidRequestError):
                _ = item.product_id
    finally:
        db.close()


def test_order_detail_endpoint_requires_authentication_before_query_validation(
    monkeypatch,
):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    configure_order_detail_test(db, None)
    try:
        missing = asyncio.run(request_order_detail(1, {"role": "admin"}))
        invalid = asyncio.run(
            request_order_detail(
                1,
                {"role": "admin"},
                headers={"Authorization": "Bearer invalid-token"},
            )
        )

        assert missing.status_code == 401
        assert invalid.status_code == 401
        assert missing.json() == {"detail": "Invalid authentication credentials"}
        assert invalid.json() == missing.json()
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_detail_endpoint_returns_exact_persisted_snapshot_contract():
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        verified_at = datetime(2026, 7, 21, 12, 5, tzinfo=UTC)
        handed_off_at = datetime(2026, 7, 21, 12, 10, tzinfo=UTC)
        order = seed_order(
            db,
            owner,
            payment_verified_at=verified_at,
            provider_handoff_sent_at=handed_off_at,
        )
        order_id = order.id
        snapshot_names = [item.display_name for item in order.items]
        products = list(db.scalars(select(Product)))
        kits = list(db.scalars(select(Kit)))
        templates = list(db.scalars(select(Template)))
        designs = list(db.scalars(select(Design)))
        for product in products:
            product.name = "Changed product"
            product.base_price = Decimal("0.01")
        for kit in kits:
            kit.name = "Changed kit"
        for template in templates:
            template.name = "Changed template"
        for design in designs:
            design.customization_values = {"changed": True}
        db.commit()
        owner_id = owner.id
        before = persistence_snapshot(db)
        db.expunge_all()
        configure_order_detail_test(db, User(id=owner_id))

        response = asyncio.run(request_order_detail(order_id))

        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == ORDER_DETAIL_FIELDS
        assert payload["id"] == order_id
        assert payload["status"] == "confirmed"
        assert payload["currency"] == "COP"
        assert payload["subtotal_amount"] == "120.00"
        assert payload["discount_amount"] == "5.00"
        assert payload["tax_amount"] == "10.00"
        assert payload["total_amount"] == "125.00"
        assert payload["payment_verified_at"] == "2026-07-21T12:05:00"
        assert payload["provider_handoff_sent_at"] == "2026-07-21T12:10:00"
        assert [item["display_name"] for item in payload["items"]] == snapshot_names
        assert [item["item_type"] for item in payload["items"]] == [
            "product",
            "kit",
            "design",
        ]
        assert all(set(item) == ORDER_DETAIL_ITEM_FIELDS for item in payload["items"])
        assert "Changed product" not in response.text
        assert "Changed kit" not in response.text
        assert "Changed template" not in response.text
        assert "internal-" not in response.text
        assert persistence_snapshot(db) == before
        assert not db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize("requested_id", [999, None])
def test_order_detail_endpoint_hides_unknown_and_cross_customer_orders(requested_id):
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        other = seed_user(db, "other@example.com")
        order = seed_order(db, owner, include_catalog_references=False)
        configure_order_detail_test(db, other)
        actual_id = order.id if requested_id is None else requested_id
        before = persistence_snapshot(db)

        response = asyncio.run(request_order_detail(actual_id))

        assert response.status_code == 404
        assert response.json() == {"detail": "Order not found"}
        assert persistence_snapshot(db) == before
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_detail_endpoint_rejects_all_query_parameters_before_repository_work(
    monkeypatch,
):
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        configure_order_detail_test(db, owner)

        def fail_if_constructed(_db):
            raise AssertionError("OrderRepository must not run")

        monkeypatch.setattr(
            "app.api.v1.endpoints.orders.OrderRepository",
            fail_if_constructed,
        )
        unsupported = {
            "customer_id": owner.id,
            "payment_status": "verified",
            "provider_reference": "forged",
            "role": "admin",
        }

        response = asyncio.run(request_order_detail(1, unsupported))

        assert response.status_code == 422
        assert response.json() == {
            "detail": {
                "code": "unsupported_query_parameter",
                "message": "Unsupported query parameter.",
                "unsupported_parameters": sorted(unsupported),
            }
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "order_status",
    [
        OrderStatus.DRAFT,
        OrderStatus.CONFIRMED,
        OrderStatus.IN_PRODUCTION,
        OrderStatus.CANCELLATION_REQUESTED,
        OrderStatus.CANCELLED,
        OrderStatus.DELIVERED,
    ],
)
def test_order_detail_endpoint_returns_persisted_lifecycle_and_nullable_timestamps(
    order_status,
):
    db = build_session()
    try:
        owner = seed_user(db, f"{order_status.value}@example.com")
        order = seed_order(
            db,
            owner,
            status=order_status,
            include_catalog_references=False,
        )
        configure_order_detail_test(db, owner)

        response = asyncio.run(request_order_detail(order.id))

        assert response.status_code == 200
        assert response.json()["status"] == order_status.value
        assert response.json()["payment_verified_at"] is None
        assert response.json()["provider_handoff_sent_at"] is None
        assert "cancellation_requested_from" not in response.json()
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_detail_endpoint_is_repeatable_and_read_only():
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        order = seed_order(db, owner, include_catalog_references=False)
        configure_order_detail_test(db, owner)
        before = persistence_snapshot(db)

        first = asyncio.run(request_order_detail(order.id))
        second = asyncio.run(request_order_detail(order.id))

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.content == second.content
        assert persistence_snapshot(db) == before
        assert not db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_detail_endpoint_documents_authenticated_safe_contract():
    async def get_openapi_schema():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/openapi.json")

    response = asyncio.run(get_openapi_schema())

    assert response.status_code == 200
    schema = response.json()
    operation = schema["paths"]["/api/v1/orders/{order_id}"]["get"]
    assert operation["summary"] == "Get customer order detail"
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"200", "401", "404", "422"} <= set(operation["responses"])
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OrderDetailRead"
    }
    assert set(schema["components"]["schemas"]["OrderDetailRead"]["properties"]) == (
        ORDER_DETAIL_FIELDS
    )
    assert (
        set(schema["components"]["schemas"]["OrderDetailItemRead"]["properties"])
        == ORDER_DETAIL_ITEM_FIELDS
    )
