import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.domain.order_lifecycle import OrderStatus
from app.domain.payment_lifecycle import PaymentStatus
from app.main import app
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.services.order_list_service import OrderListService
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


def build_session() -> Session:
    """Build an isolated in-memory database session for order list tests."""
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
    """Persist one active customer for order list endpoint tests."""
    user = User(email=email, full_name="Test Buyer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_order(
    db: Session,
    customer: User,
    *,
    created_at: datetime,
    total_amount: str = "40.00",
    currency: str = "COP",
    status: OrderStatus = OrderStatus.DRAFT,
) -> Order:
    """Persist one order with backend-owned summary snapshot values."""
    order = Order(
        customer_id=customer.id,
        status=status.value,
        subtotal_amount=Decimal(total_amount),
        discount_amount=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total_amount=Decimal(total_amount),
        currency=currency,
        payment_provider_reference="payment-internal",
        assigned_provider_id="provider-internal",
        provider_handoff_reference="handoff-internal",
        terms_policy_version="terms-internal",
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def configure_order_list_test(db: Session, current_user: User | None) -> None:
    """Install database and optional authenticated-user dependency overrides."""

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


async def request_order_list(
    params: dict[str, object] | None = None,
    *,
    headers: dict[str, str] | None = None,
):
    """Call the customer order list endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get("/api/v1/orders", params=params, headers=headers)


def order_persistence_snapshot(db: Session) -> list[tuple[object, ...]]:
    """Return persisted Order columns used to prove list reads are read-only."""
    return list(
        db.execute(
            select(
                Order.id,
                Order.customer_id,
                Order.status,
                Order.total_amount,
                Order.currency,
                Order.payment_provider_reference,
                Order.provider_handoff_reference,
                Order.terms_policy_version,
                Order.created_at,
                Order.updated_at,
            ).order_by(Order.id)
        ).all()
    )


def related_persistence_snapshot(db: Session) -> dict[str, list[tuple[object, ...]]]:
    """Return OrderItem and Payment state that list reads must not mutate."""
    return {
        "items": list(
            db.execute(
                select(
                    OrderItem.id,
                    OrderItem.order_id,
                    OrderItem.product_id,
                    OrderItem.quantity,
                    OrderItem.line_total_amount,
                    OrderItem.currency,
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
                ).order_by(Payment.id)
            ).all()
        ),
    }


def test_order_list_service_coordinates_owner_scoped_page_and_count():
    calls = []
    orders = [object(), object()]

    class FakeOrderRepository:
        def get_orders_page_for_customer(self, customer_id, *, offset, limit):
            calls.append(("list", customer_id, offset, limit))
            return orders

        def count_orders_for_customer(self, customer_id):
            calls.append(("count", customer_id))
            return 23

    page = OrderListService(FakeOrderRepository()).list_customer_orders(
        customer_id=17,
        page=3,
        page_size=10,
    )

    assert page.orders == orders
    assert page.page == 3
    assert page.page_size == 10
    assert page.total_items == 23
    assert page.total_pages == 3
    assert calls == [("list", 17, 20, 10), ("count", 17)]


def test_order_repository_pages_and_counts_only_owned_orders_with_safe_projection():
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        other = seed_user(db, "other@example.com")
        timestamp = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
        first = seed_order(db, owner, created_at=timestamp)
        second = seed_order(db, owner, created_at=timestamp)
        seed_order(db, other, created_at=timestamp + timedelta(days=1))
        owner_id = owner.id
        other_id = other.id
        first_id = first.id
        second_id = second.id
        db.expunge_all()

        repository = OrderRepository(db)
        orders = repository.get_orders_page_for_customer(
            owner_id,
            offset=0,
            limit=20,
        )

        assert [order.id for order in orders] == [second_id, first_id]
        assert repository.count_orders_for_customer(owner_id) == 2
        assert repository.count_orders_for_customer(other_id) == 1
        for order in orders:
            state = inspect(order)
            assert {"customer", "items", "payments"} <= state.unloaded
            assert {
                "id",
                "status",
                "currency",
                "total_amount",
                "created_at",
                "updated_at",
            }.isdisjoint(state.unloaded)
    finally:
        db.close()


def test_order_list_endpoint_requires_authentication_and_rejects_invalid_token(
    monkeypatch,
):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    configure_order_list_test(db, None)
    try:
        missing_response = asyncio.run(request_order_list())
        invalid_response = asyncio.run(
            request_order_list(headers={"Authorization": "Bearer invalid-token"})
        )

        assert missing_response.status_code == 401
        assert invalid_response.status_code == 401
        assert missing_response.json() == {
            "detail": "Invalid authentication credentials"
        }
        assert invalid_response.json() == missing_response.json()
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_list_endpoint_returns_exact_empty_default_page():
    db = build_session()
    try:
        customer = seed_user(db, "buyer@example.com")
        configure_order_list_test(db, customer)

        response = asyncio.run(request_order_list())

        assert response.status_code == 200
        assert response.json() == {
            "data": [],
            "meta": {
                "page": 1,
                "page_size": 20,
                "total_items": 0,
                "total_pages": 0,
            },
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_list_endpoint_isolates_owner_data_and_metadata():
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        other = seed_user(db, "other@example.com")
        timestamp = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
        owned_order = seed_order(
            db,
            owner,
            created_at=timestamp,
            total_amount="85.00",
            status=OrderStatus.CONFIRMED,
        )
        seed_order(db, other, created_at=timestamp + timedelta(days=1))
        seed_order(db, other, created_at=timestamp + timedelta(days=2))
        configure_order_list_test(db, owner)

        response = asyncio.run(request_order_list())

        assert response.status_code == 200
        payload = response.json()
        assert [order["id"] for order in payload["data"]] == [owned_order.id]
        assert payload["meta"] == {
            "page": 1,
            "page_size": 20,
            "total_items": 1,
            "total_pages": 1,
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_list_endpoint_orders_by_created_at_then_id_descending():
    db = build_session()
    try:
        customer = seed_user(db, "buyer@example.com")
        timestamp = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
        oldest = seed_order(db, customer, created_at=timestamp - timedelta(days=1))
        first_tied = seed_order(db, customer, created_at=timestamp)
        second_tied = seed_order(db, customer, created_at=timestamp)
        configure_order_list_test(db, customer)

        response = asyncio.run(request_order_list())

        assert response.status_code == 200
        assert [order["id"] for order in response.json()["data"]] == [
            second_tied.id,
            first_tied.id,
            oldest.id,
        ]
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_list_endpoint_paginates_and_preserves_totals_beyond_last_page():
    db = build_session()
    try:
        customer = seed_user(db, "buyer@example.com")
        timestamp = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
        orders = [
            seed_order(db, customer, created_at=timestamp + timedelta(minutes=index))
            for index in range(5)
        ]
        configure_order_list_test(db, customer)

        second_page = asyncio.run(request_order_list({"page": 2, "page_size": 2}))
        beyond_page = asyncio.run(request_order_list({"page": 4, "page_size": 2}))

        assert second_page.status_code == 200
        assert [order["id"] for order in second_page.json()["data"]] == [
            orders[2].id,
            orders[1].id,
        ]
        assert second_page.json()["meta"] == {
            "page": 2,
            "page_size": 2,
            "total_items": 5,
            "total_pages": 3,
        }
        assert beyond_page.status_code == 200
        assert beyond_page.json() == {
            "data": [],
            "meta": {
                "page": 4,
                "page_size": 2,
                "total_items": 5,
                "total_pages": 3,
            },
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": -1},
        {"page_size": 0},
        {"page_size": -1},
        {"page_size": 101},
    ],
)
def test_order_list_endpoint_rejects_invalid_pagination_before_repository_work(
    params,
    monkeypatch,
):
    db = build_session()
    try:
        customer = seed_user(db, "buyer@example.com")
        configure_order_list_test(db, customer)

        def fail_if_constructed(_db):
            raise AssertionError("OrderRepository must not run")

        monkeypatch.setattr(
            "app.api.v1.endpoints.orders.OrderRepository",
            fail_if_constructed,
        )

        response = asyncio.run(request_order_list(params))

        assert response.status_code == 422
        assert order_persistence_snapshot(db) == []
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_list_endpoint_rejects_sorted_unsupported_claims_before_repository_work(
    monkeypatch,
):
    db = build_session()
    try:
        customer = seed_user(db, "buyer@example.com")
        configure_order_list_test(db, customer)

        def fail_if_constructed(_db):
            raise AssertionError("OrderRepository must not run")

        monkeypatch.setattr(
            "app.api.v1.endpoints.orders.OrderRepository",
            fail_if_constructed,
        )
        unsupported = {
            "status": "confirmed",
            "created_after": "2026-01-01",
            "payment_status": "paid",
            "provider_id": "forged",
            "customer_id": customer.id,
            "item_type": "product",
            "total_amount": "0.01",
            "role": "admin",
        }

        response = asyncio.run(request_order_list(unsupported))

        assert response.status_code == 422
        assert response.json() == {
            "detail": {
                "code": "unsupported_query_parameter",
                "message": "Unsupported query parameter.",
                "unsupported_parameters": sorted(unsupported),
            }
        }
        assert order_persistence_snapshot(db) == []
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_list_endpoint_exposes_only_persisted_safe_summary_fields():
    db = build_session()
    try:
        customer = seed_user(db, "buyer@example.com")
        timestamp = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
        order = seed_order(
            db,
            customer,
            created_at=timestamp,
            total_amount="85.75",
            currency="USD",
            status=OrderStatus.CONFIRMED,
        )
        category = Category(name="Mutable catalog", description=None)
        product = Product(
            name="Original catalog name",
            description=None,
            category=category,
            base_price=Decimal("10.00"),
        )
        order.items = [
            OrderItem(
                item_type="product",
                product=product,
                display_name="Persisted item snapshot",
                customer_safe_description=None,
                selected_options={},
                quantity=1,
                unit_price_amount=Decimal("85.75"),
                line_subtotal_amount=Decimal("85.75"),
                line_discount_amount=Decimal("0.00"),
                line_tax_amount=Decimal("0.00"),
                line_total_amount=Decimal("85.75"),
                currency="USD",
                assigned_provider_id="provider-internal",
                provider_pricing_reference="pricing-internal",
                provider_payload_snapshot={"internal": "provider-only"},
            )
        ]
        order.payments = [
            Payment(
                provider_code="legacy_generic",
                merchant_reference=f"legacy-list-{order.id}",
                status=PaymentStatus.VERIFIED.value,
                amount=Decimal("85.75"),
                currency="USD",
                payment_provider_reference="payment-internal",
                verified_at=timestamp,
            )
        ]
        db.add(order)
        db.commit()
        product.name = "Changed catalog name"
        product.base_price = Decimal("999.99")
        db.commit()
        configure_order_list_test(db, customer)
        orders_before = order_persistence_snapshot(db)
        related_before = related_persistence_snapshot(db)

        response = asyncio.run(request_order_list())

        assert response.status_code == 200
        summary = response.json()["data"][0]
        assert set(summary) == {
            "id",
            "status",
            "currency",
            "total_amount",
            "created_at",
            "updated_at",
        }
        assert summary["id"] == order.id
        assert summary["status"] == "confirmed"
        assert summary["currency"] == "USD"
        assert summary["total_amount"] == "85.75"
        assert "internal" not in response.text
        assert order_persistence_snapshot(db) == orders_before
        assert related_persistence_snapshot(db) == related_before
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_list_endpoint_is_repeatable_and_read_only():
    db = build_session()
    try:
        customer = seed_user(db, "buyer@example.com")
        seed_order(
            db,
            customer,
            created_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
            status=OrderStatus.CONFIRMED,
        )
        configure_order_list_test(db, customer)
        before = order_persistence_snapshot(db)

        first_response = asyncio.run(request_order_list())
        second_response = asyncio.run(request_order_list())

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert first_response.content == second_response.content
        assert order_persistence_snapshot(db) == before
        assert not db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_order_list_endpoint_documents_safe_authenticated_paginated_contract():
    async def get_openapi_schema():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/openapi.json")

    schema_response = asyncio.run(get_openapi_schema())

    assert schema_response.status_code == 200
    schema = schema_response.json()
    operation = schema["paths"]["/api/v1/orders"]["get"]
    assert operation["summary"] == "List customer orders"
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "page",
        "page_size",
    }
    assert operation["security"] == [{"HTTPBearer": []}]
    assert {"200", "401", "422"} <= set(operation["responses"])
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/OrderListResponse"
    }
    assert {
        "OrderSummaryRead",
        "OrderListMeta",
        "OrderListResponse",
    } <= set(schema["components"]["schemas"])
    assert set(schema["components"]["schemas"]["OrderSummaryRead"]["properties"]) == {
        "id",
        "status",
        "currency",
        "total_amount",
        "created_at",
        "updated_at",
    }
    assert schema["components"]["schemas"]["OrderListResponse"]["properties"]["data"][
        "items"
    ] == {"$ref": "#/components/schemas/OrderSummaryRead"}
