import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.core.database import Base, get_db
from app.domain.order_lifecycle import OrderStatus
from app.main import app
from app.models.audit_log import AuditLog
from app.models.order import Order
from app.models.user import User, UserRole
from app.services.order_cancellation_service import (
    ADMIN_CANCELLATION_APPROVAL_AUDIT_ACTION,
    ADMIN_CANCELLATION_REJECTION_AUDIT_ACTION,
    CUSTOMER_CANCELLATION_REQUEST_AUDIT_ACTION,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for cancellation endpoint tests."""
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


def seed_user(db, *, email: str, role: str = UserRole.USER) -> User:
    """Persist one active user for cancellation endpoint authorization tests."""
    user = User(email=email, full_name="Test Buyer", role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_order(
    db,
    *,
    customer_id: int,
    status: OrderStatus = OrderStatus.CONFIRMED,
    cancellation_requested_from: OrderStatus | None = None,
) -> Order:
    """Persist one paid order candidate for cancellation endpoint tests."""
    order = Order(
        customer_id=customer_id,
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
        payment_verified_at=datetime(2026, 6, 10, tzinfo=UTC),
        assigned_provider_id="local-provider",
        provider_handoff_reference="local-order-1",
        provider_handoff_sent_at=datetime(2026, 6, 10, tzinfo=UTC),
        terms_policy_version="terms-v1",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


async def post_cancellation_request(order_id: int, payload: dict[str, object]):
    """Call the customer cancellation request endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            f"/api/v1/orders/{order_id}/cancellation-request",
            json=payload,
        )


async def post_cancellation_approval(order_id: int, payload: dict[str, object]):
    """Call the admin cancellation approval endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            f"/api/v1/orders/{order_id}/cancellation-request/approve",
            json=payload,
        )


async def post_cancellation_rejection(order_id: int, payload: dict[str, object]):
    """Call the admin cancellation rejection endpoint through ASGI transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post(
            f"/api/v1/orders/{order_id}/cancellation-request/reject",
            json=payload,
        )


def configure_order_endpoint_test(db, current_user: User | None) -> None:
    """Install dependency overrides for a cancellation endpoint test."""

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


def table_count(db, model) -> int:
    """Return the number of persisted rows for a model."""
    return db.scalar(select(func.count()).select_from(model))


@pytest.mark.parametrize(
    "starting_status",
    [
        OrderStatus.CONFIRMED,
        OrderStatus.ACCEPTED,
        OrderStatus.IN_PRODUCTION,
    ],
)
def test_customer_endpoint_records_cancellation_request_and_audit_log(starting_status):
    db = build_session()
    try:
        customer = seed_user(db, email="buyer@example.com")
        order = seed_order(db, customer_id=customer.id, status=starting_status)
        configure_order_endpoint_test(db, customer)

        response = asyncio.run(post_cancellation_request(order.id, {}))

        assert response.status_code == 200
        assert response.json() == {
            "order_id": order.id,
            "order_status": OrderStatus.CANCELLATION_REQUESTED.value,
            "cancellation_requested_from": starting_status.value,
            "customer_safe_status": OrderStatus.CANCELLATION_REQUESTED.value,
        }
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CANCELLATION_REQUESTED.value
        assert stored_order.cancellation_requested_from == starting_status.value
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        audit_log = db.scalar(select(AuditLog))
        assert audit_log.action == CUSTOMER_CANCELLATION_REQUEST_AUDIT_ACTION
        assert audit_log.event_details["actor_type"] == "customer"
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "starting_status",
    [
        OrderStatus.DRAFT,
        OrderStatus.SENT_TO_PROVIDER,
        OrderStatus.READY_FOR_PICKUP,
        OrderStatus.SHIPPED,
        OrderStatus.DELIVERED,
    ],
)
def test_customer_endpoint_rejects_ineligible_request_without_mutation(starting_status):
    db = build_session()
    try:
        customer = seed_user(db, email="buyer@example.com")
        order = seed_order(db, customer_id=customer.id, status=starting_status)
        configure_order_endpoint_test(db, customer)

        response = asyncio.run(post_cancellation_request(order.id, {}))

        assert response.status_code == 400
        assert response.json()["detail"]["code"] == "order_cancellation_not_allowed"
        assert db.get(Order, order.id).status == starting_status.value
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_cross_user_cancellation_request_is_rejected():
    db = build_session()
    try:
        owner = seed_user(db, email="buyer@example.com")
        other_user = seed_user(db, email="other@example.com")
        order = seed_order(db, customer_id=owner.id, status=OrderStatus.CONFIRMED)
        configure_order_endpoint_test(db, other_user)

        response = asyncio.run(post_cancellation_request(order.id, {}))

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "order_not_found"
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_unauthenticated_cancellation_request_is_rejected():
    db = build_session()
    try:
        owner = seed_user(db, email="buyer@example.com")
        order = seed_order(db, customer_id=owner.id, status=OrderStatus.CONFIRMED)
        configure_order_endpoint_test(db, None)

        response = asyncio.run(post_cancellation_request(order.id, {}))

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authentication credentials"}
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_customer_cannot_directly_force_cancelled_status_or_admin_claims():
    db = build_session()
    try:
        customer = seed_user(db, email="buyer@example.com")
        order = seed_order(db, customer_id=customer.id, status=OrderStatus.CONFIRMED)
        configure_order_endpoint_test(db, customer)

        response = asyncio.run(
            post_cancellation_request(
                order.id,
                {
                    "status": "cancelled",
                    "cancellation_requested_from": "confirmed",
                    "role": "admin",
                    "is_admin": True,
                },
            )
        )

        assert response.status_code == 422
        assert db.get(Order, order.id).status == OrderStatus.CONFIRMED.value
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_admin_approval_moves_request_to_cancelled_and_audits():
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(
            db,
            customer_id=1,
            status=OrderStatus.CANCELLATION_REQUESTED,
            cancellation_requested_from=OrderStatus.ACCEPTED,
        )
        configure_order_endpoint_test(db, admin)

        response = asyncio.run(post_cancellation_approval(order.id, {}))

        assert response.status_code == 200
        assert response.json() == {
            "order_id": order.id,
            "order_status": OrderStatus.CANCELLED.value,
            "cancellation_requested_from": None,
            "customer_safe_status": OrderStatus.CANCELLED.value,
        }
        stored_order = db.get(Order, order.id)
        assert stored_order.status == OrderStatus.CANCELLED.value
        assert stored_order.cancellation_requested_from is None
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        audit_log = db.scalar(select(AuditLog))
        assert audit_log.action == ADMIN_CANCELLATION_APPROVAL_AUDIT_ACTION
        assert audit_log.event_details["actor_type"] == "admin"
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    "original_status",
    [
        OrderStatus.CONFIRMED,
        OrderStatus.ACCEPTED,
        OrderStatus.IN_PRODUCTION,
    ],
)
def test_admin_rejection_restores_original_status_and_audits(original_status):
    db = build_session()
    try:
        admin = seed_user(db, email="admin@example.com", role=UserRole.ADMIN)
        order = seed_order(
            db,
            customer_id=1,
            status=OrderStatus.CANCELLATION_REQUESTED,
            cancellation_requested_from=original_status,
        )
        configure_order_endpoint_test(db, admin)

        response = asyncio.run(post_cancellation_rejection(order.id, {}))

        assert response.status_code == 200
        assert response.json() == {
            "order_id": order.id,
            "order_status": original_status.value,
            "cancellation_requested_from": None,
            "customer_safe_status": original_status.value,
        }
        stored_order = db.get(Order, order.id)
        assert stored_order.status == original_status.value
        assert stored_order.cancellation_requested_from is None
        assert stored_order.payment_provider_reference == "pay_internal_ref"
        audit_log = db.scalar(select(AuditLog))
        assert audit_log.action == ADMIN_CANCELLATION_REJECTION_AUDIT_ACTION
        assert audit_log.event_details["actor_type"] == "admin"
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_non_admin_user_cannot_approve_or_reject_cancellation_request():
    db = build_session()
    try:
        customer = seed_user(db, email="buyer@example.com", role=UserRole.USER)
        order = seed_order(
            db,
            customer_id=customer.id,
            status=OrderStatus.CANCELLATION_REQUESTED,
            cancellation_requested_from=OrderStatus.CONFIRMED,
        )
        configure_order_endpoint_test(db, customer)

        approval_response = asyncio.run(post_cancellation_approval(order.id, {}))
        rejection_response = asyncio.run(post_cancellation_rejection(order.id, {}))

        assert approval_response.status_code == 403
        assert rejection_response.status_code == 403
        assert db.get(Order, order.id).status == OrderStatus.CANCELLATION_REQUESTED.value
        assert table_count(db, AuditLog) == 0
    finally:
        app.dependency_overrides.clear()
        db.close()
