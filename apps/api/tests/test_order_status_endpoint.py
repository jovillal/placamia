import asyncio
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.core.database import Base, get_db
from app.domain.order_lifecycle import OrderStatus
from app.main import app
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for order status tests."""
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


def seed_user(db, email: str) -> User:
    """Persist one active user for order status endpoint tests."""
    user = User(email=email, full_name="Test Buyer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_product(db) -> Product:
    """Persist one product used as traceability for order item snapshots."""
    category = Category(name="Emergency", description=None)
    product = Product(
        name="Current catalog name",
        description="Current catalog description",
        category=category,
        base_price=Decimal("20.00"),
        is_active=True,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def seed_order(
    db,
    customer: User,
    product: Product,
    *,
    status: OrderStatus = OrderStatus.DRAFT,
    cancellation_requested_from: OrderStatus | None = None,
) -> Order:
    """Persist one order with a customer-safe item snapshot."""
    order = Order(
        customer_id=customer.id,
        status=status.value,
        cancellation_requested_from=(
            cancellation_requested_from.value
            if cancellation_requested_from is not None
            else None
        ),
        subtotal_amount=Decimal("40.00"),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal("40.00"),
        currency="COP",
        payment_provider_reference="pay_internal_ref",
        assigned_provider_id="local-provider",
        provider_handoff_reference="handoff_internal_ref",
        terms_policy_version="terms-v1",
    )
    order.items = [
        OrderItem(
            item_type="product",
            product_id=product.id,
            display_name="Checkout-captured product name",
            customer_safe_description="Checkout-captured description",
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
                "internal": "provider-only",
                "provider_quote_reference": "local-quote-product-1",
            },
        )
    ]
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


async def get_order_status(order_id: int, query: str = ""):
    """Call the order status endpoint through ASGI test transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(f"/api/v1/orders/{order_id}/status{query}")


def configure_order_status_test(db, current_user: User | None) -> None:
    """Install FastAPI dependency overrides for an order status endpoint test."""

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


def test_order_status_endpoint_returns_customer_safe_owned_order_status():
    db = build_session()
    try:
        user = seed_user(db, "buyer@example.com")
        product = seed_product(db)
        order = seed_order(db, user, product, status=OrderStatus.CONFIRMED)
        configure_order_status_test(db, user)

        response = asyncio.run(get_order_status(order.id))

        assert response.status_code == 200
        payload = response.json()
        assert payload["id"] == order.id
        assert payload["status"] == OrderStatus.CONFIRMED.value
        assert payload["cancellation_requested_from"] is None
        assert payload["total_amount"] == "40.00"
        assert payload["currency"] == "COP"
        assert len(payload["items"]) == 1
        item_payload = payload["items"][0]
        assert item_payload == {
            "id": order.items[0].id,
            "item_type": "product",
            "product_id": product.id,
            "kit_id": None,
            "template_id": None,
            "design_id": None,
            "display_name": "Checkout-captured product name",
            "customer_safe_description": "Checkout-captured description",
            "selected_options": {"material": "acrylic", "size": "20x30"},
            "quantity": 2,
            "line_total_amount": "40.00",
            "currency": "COP",
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_status_endpoint_rejects_unauthenticated_access():
    db = build_session()
    try:
        user = seed_user(db, "buyer@example.com")
        product = seed_product(db)
        order = seed_order(db, user, product)
        configure_order_status_test(db, None)

        response = asyncio.run(get_order_status(order.id))

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authentication credentials"}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_status_endpoint_returns_safe_not_found_for_cross_user_access():
    db = build_session()
    try:
        owner = seed_user(db, "buyer@example.com")
        other_user = seed_user(db, "other@example.com")
        product = seed_product(db)
        order = seed_order(db, owner, product)
        configure_order_status_test(db, other_user)

        response = asyncio.run(get_order_status(order.id))

        assert response.status_code == 404
        assert response.json() == {"detail": "Order not found"}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_status_endpoint_ignores_frontend_ownership_claims():
    db = build_session()
    try:
        owner = seed_user(db, "buyer@example.com")
        other_user = seed_user(db, "other@example.com")
        product = seed_product(db)
        order = seed_order(db, owner, product)
        configure_order_status_test(db, other_user)

        response = asyncio.run(
            get_order_status(
                order.id,
                "?customer_id=1&user_id=1&owner_id=1&role=admin&is_admin=true",
            )
        )

        assert response.status_code == 404
        assert response.json() == {"detail": "Order not found"}
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "order_status",
    [
        OrderStatus.READY_FOR_PICKUP,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
        OrderStatus.CANCELLED,
    ],
)
def test_order_status_endpoint_returns_customer_safe_lifecycle_states(order_status):
    db = build_session()
    try:
        user = seed_user(db, "buyer@example.com")
        product = seed_product(db)
        order = seed_order(db, user, product, status=order_status)
        configure_order_status_test(db, user)

        response = asyncio.run(get_order_status(order.id))

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == order_status.value
        assert payload["cancellation_requested_from"] is None
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_status_endpoint_represents_cancellation_request_safely():
    db = build_session()
    try:
        user = seed_user(db, "buyer@example.com")
        product = seed_product(db)
        order = seed_order(
            db,
            user,
            product,
            status=OrderStatus.CANCELLATION_REQUESTED,
            cancellation_requested_from=OrderStatus.ACCEPTED,
        )
        configure_order_status_test(db, user)

        response = asyncio.run(get_order_status(order.id))

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == OrderStatus.CANCELLATION_REQUESTED.value
        assert payload["cancellation_requested_from"] == OrderStatus.ACCEPTED.value
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_status_response_omits_provider_payment_and_internal_fields():
    db = build_session()
    try:
        user = seed_user(db, "buyer@example.com")
        product = seed_product(db)
        order = seed_order(db, user, product, status=OrderStatus.CANCELLED)
        configure_order_status_test(db, user)

        response = asyncio.run(get_order_status(order.id))

        assert response.status_code == 200
        payload = response.json()
        forbidden_order_fields = {
            "customer_id",
            "payment_provider_reference",
            "payment_verified_at",
            "assigned_provider_id",
            "provider_handoff_reference",
            "provider_handoff_sent_at",
            "terms_policy_version",
        }
        forbidden_item_fields = {
            "assigned_provider_id",
            "provider_pricing_reference",
            "provider_payload_snapshot",
            "unit_price_amount",
            "line_subtotal_amount",
            "line_discount_amount",
            "line_tax_amount",
        }
        assert forbidden_order_fields.isdisjoint(payload)
        assert forbidden_item_fields.isdisjoint(payload["items"][0])
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_status_endpoint_does_not_mutate_order_state():
    db = build_session()
    try:
        user = seed_user(db, "buyer@example.com")
        product = seed_product(db)
        order = seed_order(db, user, product, status=OrderStatus.CONFIRMED)
        configure_order_status_test(db, user)

        response = asyncio.run(get_order_status(order.id))

        assert response.status_code == 200
        stored_order = db.get(Order, order.id)
        assert stored_order is not None
        assert stored_order.status == OrderStatus.CONFIRMED.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        assert stored_order.provider_handoff_reference == "handoff_internal_ref"
        assert stored_order.items[0].provider_payload_snapshot == {
            "internal": "provider-only",
            "provider_quote_reference": "local-quote-product-1",
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_status_endpoint_is_documented_in_openapi():
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
    operation = schema["paths"]["/api/v1/orders/{order_id}/status"]["get"]
    assert operation["summary"] == "Get order status"
    assert "200" in operation["responses"]
