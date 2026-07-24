import asyncio
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import (
    get_current_user,
    get_payment_provider_runtime_factory,
    get_provider_adapter,
)
from app.core.database import Base, get_db
from app.domain.payment_provider_gateway import CheckoutRequest
from app.domain.provider_adapter import (
    AvailabilityState,
    CatalogItemType,
    LocalMockProviderAdapter,
    LocalProviderFixture,
)
from app.main import app
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.payment import Payment
from app.models.product import Product
from app.models.user import User
from app.services.payment_provider_registry import (
    PaymentProviderRegistry,
    PaymentProviderRuntime,
)
from app.services.wompi_payment_provider import WompiPaymentProvider
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker


class SlowWompiPaymentProvider(WompiPaymentProvider):
    """Hold the Order lock briefly so the competing request must wait."""

    async def initialize_checkout(self, request: CheckoutRequest):
        """Delay local construction without adding an external provider call."""
        time.sleep(0.2)
        return await super().initialize_checkout(request)


class ConcurrencyPaymentRuntimeFactory:
    """Return deterministic Wompi runtime configuration for the race test."""

    def __init__(self) -> None:
        """Build one stateless local Wompi checkout adapter."""
        provider = SlowWompiPaymentProvider(
            public_key="pub_test_concurrency-key",
            integrity_secret="test_integrity_concurrency-secret",
            approved_return_url="http://localhost:3000/payments/return",
        )
        self._runtime = PaymentProviderRuntime(
            registry=PaymentProviderRegistry({"wompi": provider}, "wompi"),
            return_url="http://localhost:3000/payments/return",
            checkout_ttl_seconds=1800,
        )

    def create(self) -> PaymentProviderRuntime:
        """Return validated deterministic runtime without side effects."""
        return self._runtime


def _postgres_test_url() -> str:
    """Return the dedicated test database URL or skip only outside CI."""
    database_url = os.getenv("TEST_POSTGRES_DATABASE_URL")
    if database_url is None:
        if os.getenv("CI"):
            pytest.fail("TEST_POSTGRES_DATABASE_URL is required in CI")
        pytest.skip("Dedicated PostgreSQL concurrency database is not configured")
    database_name = make_url(database_url).database or ""
    if "test" not in database_name:
        pytest.fail("Concurrency test requires a dedicated test database")
    return database_url


def _seed_checkout(session_factory) -> tuple[User, Order, Product]:
    """Persist one owner-scoped, payment-ready Order in PostgreSQL."""
    with session_factory() as db:
        user = User(email="concurrency@example.com", full_name="Concurrency Buyer")
        category = Category(name="Concurrency category", description=None)
        product = Product(
            name="Concurrency product",
            description=None,
            category=category,
            base_price=Decimal("20.00"),
            is_active=True,
        )
        order = Order(
            customer=user,
            status="draft",
            subtotal_amount=Decimal("40.00"),
            discount_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("40.00"),
            currency="COP",
            assigned_provider_id="local-provider",
            terms_policy_version="terms-v1",
        )
        order.items = [
            OrderItem(
                item_type="product",
                product=product,
                display_name="Concurrency snapshot",
                customer_safe_description=None,
                selected_options={},
                quantity=2,
                unit_price_amount=Decimal("20.00"),
                line_subtotal_amount=Decimal("40.00"),
                line_discount_amount=Decimal("0.00"),
                line_tax_amount=Decimal("0.00"),
                line_total_amount=Decimal("40.00"),
                currency="COP",
                assigned_provider_id="local-provider",
                provider_pricing_reference="local-quote-product-1",
                provider_payload_snapshot={"safe": True},
            )
        ]
        db.add(order)
        db.commit()
        db.refresh(user)
        db.refresh(order)
        db.refresh(product)
        db.expunge_all()
        return user, order, product


def test_concurrent_first_initialization_creates_one_active_wompi_payment():
    """Prove PostgreSQL row locking serializes independent first requests."""
    engine = create_engine(_postgres_test_url())
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    user, order, product = _seed_checkout(session_factory)

    async def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    async def override_get_current_user():
        return user

    async def override_get_provider_adapter():
        return LocalMockProviderAdapter(
            {
                (CatalogItemType.PRODUCT, product.id): LocalProviderFixture(
                    availability_state=AvailabilityState.AVAILABLE,
                    provider_cost=Decimal("12.00"),
                    supports_requested_configuration=True,
                )
            }
        )

    async def override_get_payment_provider_runtime_factory():
        return ConcurrencyPaymentRuntimeFactory()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_provider_adapter] = override_get_provider_adapter
    app.dependency_overrides[get_payment_provider_runtime_factory] = (
        override_get_payment_provider_runtime_factory
    )
    request_barrier = threading.Barrier(2)

    async def post_payment():
        request_barrier.wait()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.post(
                "/api/v1/payments",
                json={"order_id": order.id},
            )

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(lambda _index: asyncio.run(post_payment()), range(2))
            )

        assert sorted(response.status_code for response in responses) == [200, 201]
        payloads = [response.json()["data"] for response in responses]
        assert len({payload["payment_id"] for payload in payloads}) == 1
        assert len({payload["handoff"]["url"] for payload in payloads}) == 1

        with session_factory() as db:
            payments = list(
                db.scalars(
                    select(Payment)
                    .where(Payment.order_id == order.id)
                    .order_by(Payment.id)
                )
            )
            assert len(payments) == 1
            assert payments[0].status == "requires_action"
            assert payments[0].provider_code == "wompi"
            assert payments[0].merchant_reference == (
                f"placamia-payment-{payments[0].id}"
            )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
