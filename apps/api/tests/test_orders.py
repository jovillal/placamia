from decimal import Decimal

import pytest
from app.core.database import Base
from app.domain.order_lifecycle import OrderStatus
from app.models.category import Category
from app.models.order import Order
from app.models.order_item import OrderItem, OrderItemType
from app.models.product import Product
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
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


def create_customer(db, email: str = "buyer@example.com") -> User:
    customer = User(email=email, full_name="Test Buyer")
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def create_product(db, name: str = "Exit route sign") -> Product:
    category = Category(name="Emergency", description=None)
    product = Product(
        name=name,
        description="Catalog description",
        category=category,
        base_price=Decimal("12.50"),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def build_order(customer: User, **overrides) -> Order:
    values = {
        "customer_id": customer.id,
        "status": OrderStatus.DRAFT.value,
        "subtotal_amount": Decimal("50.00"),
        "discount_amount": Decimal("5.00"),
        "tax_amount": Decimal("9.50"),
        "total_amount": Decimal("54.50"),
        "currency": "COP",
        "assigned_provider_id": "local-provider",
        "terms_policy_version": "local-terms-v1",
    }
    values.update(overrides)
    return Order(**values)


def build_order_item(product: Product, **overrides) -> OrderItem:
    values = {
        "item_type": OrderItemType.PRODUCT,
        "product_id": product.id,
        "display_name": product.name,
        "customer_safe_description": product.description,
        "selected_options": {
            "material": "acrylic",
            "size": "20x30",
            "finish": "reflective",
        },
        "quantity": 2,
        "unit_price_amount": Decimal("25.00"),
        "line_subtotal_amount": Decimal("50.00"),
        "line_discount_amount": Decimal("5.00"),
        "line_tax_amount": Decimal("9.50"),
        "line_total_amount": Decimal("54.50"),
        "currency": "COP",
        "assigned_provider_id": "local-provider",
        "provider_pricing_reference": "local-quote-product-1",
        "provider_payload_snapshot": {
            "display_name": product.name,
            "material": "acrylic",
            "size": "20x30",
            "quantity": 2,
        },
    }
    values.update(overrides)
    return OrderItem(**values)


def test_order_repository_creates_draft_order_with_item_snapshot():
    db = build_session()
    try:
        customer = create_customer(db)
        product = create_product(db)
        repository = OrderRepository(db)

        order = repository.create_order(
            build_order(customer),
            [build_order_item(product)],
        )

        assert order.id == 1
        assert order.customer_id == customer.id
        assert order.customer == customer
        assert order.status == OrderStatus.DRAFT.value
        assert order.cancellation_requested_from is None
        assert order.subtotal_amount == Decimal("50.00")
        assert order.discount_amount == Decimal("5.00")
        assert order.tax_amount == Decimal("9.50")
        assert order.total_amount == Decimal("54.50")
        assert order.currency == "COP"
        assert order.terms_policy_version == "local-terms-v1"
        assert order.created_at is not None
        assert order.updated_at is not None

        assert len(order.items) == 1
        item = order.items[0]
        assert item.id == 1
        assert item.order_id == order.id
        assert item.product_id == product.id
        assert item.display_name == "Exit route sign"
        assert item.quantity == 2
        assert item.unit_price_amount == Decimal("25.00")
        assert item.line_total_amount == Decimal("54.50")
        assert item.assigned_provider_id == "local-provider"
        assert item.provider_pricing_reference == "local-quote-product-1"
        assert item.provider_payload_snapshot["display_name"] == "Exit route sign"
        assert item.created_at is not None
    finally:
        db.close()


def test_order_repository_retrieves_orders_by_id_and_customer():
    db = build_session()
    try:
        customer = create_customer(db)
        other_customer = create_customer(db, "other@example.com")
        product = create_product(db)
        repository = OrderRepository(db)
        order = repository.create_order(
            build_order(customer), [build_order_item(product)]
        )
        repository.create_order(
            build_order(
                other_customer,
                subtotal_amount=Decimal("1.00"),
                total_amount=Decimal("1.00"),
            ),
            [
                build_order_item(
                    product,
                    line_subtotal_amount=Decimal("1.00"),
                    line_total_amount=Decimal("1.00"),
                )
            ],
        )

        assert repository.get_order_by_id(order.id) == order
        assert repository.get_order_by_id(999) is None
        assert repository.get_orders_for_customer(customer.id) == [order]
    finally:
        db.close()


def test_order_and_order_item_tables_match_path_a_fields():
    db = build_session()
    try:
        order_columns = {
            column["name"] for column in inspect(db.bind).get_columns("orders")
        }
        item_columns = {
            column["name"] for column in inspect(db.bind).get_columns("order_items")
        }

        assert order_columns == {
            "id",
            "customer_id",
            "status",
            "cancellation_requested_from",
            "subtotal_amount",
            "discount_amount",
            "tax_amount",
            "total_amount",
            "currency",
            "payment_provider_reference",
            "payment_verified_at",
            "assigned_provider_id",
            "provider_handoff_reference",
            "provider_handoff_sent_at",
            "terms_policy_version",
            "created_at",
            "updated_at",
        }
        assert item_columns == {
            "id",
            "order_id",
            "item_type",
            "product_id",
            "kit_id",
            "template_id",
            "design_id",
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
            "assigned_provider_id",
            "provider_pricing_reference",
            "provider_payload_snapshot",
            "created_at",
        }
    finally:
        db.close()


def test_order_status_constraint_rejects_unsupported_status():
    db = build_session()
    try:
        customer = create_customer(db)
        db.add(build_order(customer, status="frontend_claimed_paid"))

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_order_item_type_constraint_rejects_unsupported_item_type():
    db = build_session()
    try:
        customer = create_customer(db)
        product = create_product(db)
        order = build_order(customer)
        order.items = [build_order_item(product, item_type="subscription")]
        db.add(order)

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_required_order_fields_are_enforced():
    db = build_session()
    try:
        db.add(
            Order(
                status=OrderStatus.DRAFT.value,
                subtotal_amount=Decimal("50.00"),
                total_amount=Decimal("50.00"),
                currency="COP",
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_pricing_snapshot_fields_are_persisted_from_backend_values():
    db = build_session()
    try:
        customer = create_customer(db)
        product = create_product(db)
        repository = OrderRepository(db)

        order = repository.create_order(
            build_order(
                customer,
                subtotal_amount=Decimal("100.00"),
                discount_amount=Decimal("10.00"),
                tax_amount=Decimal("17.10"),
                total_amount=Decimal("107.10"),
            ),
            [
                build_order_item(
                    product,
                    unit_price_amount=Decimal("50.00"),
                    line_subtotal_amount=Decimal("100.00"),
                    line_discount_amount=Decimal("10.00"),
                    line_tax_amount=Decimal("17.10"),
                    line_total_amount=Decimal("107.10"),
                )
            ],
        )

        item = order.items[0]
        assert order.subtotal_amount == Decimal("100.00")
        assert order.discount_amount == Decimal("10.00")
        assert order.tax_amount == Decimal("17.10")
        assert order.total_amount == Decimal("107.10")
        assert item.unit_price_amount == Decimal("50.00")
        assert item.line_subtotal_amount == Decimal("100.00")
        assert item.line_discount_amount == Decimal("10.00")
        assert item.line_tax_amount == Decimal("17.10")
        assert item.line_total_amount == Decimal("107.10")
    finally:
        db.close()


def test_cancellation_requested_from_is_persisted_for_cancellation_requested_order():
    db = build_session()
    try:
        customer = create_customer(db)
        order = build_order(
            customer,
            status=OrderStatus.CANCELLATION_REQUESTED.value,
            cancellation_requested_from=OrderStatus.CONFIRMED.value,
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        assert order.status == OrderStatus.CANCELLATION_REQUESTED.value
        assert order.cancellation_requested_from == OrderStatus.CONFIRMED.value
    finally:
        db.close()


def test_cancellation_requested_from_is_nullable_for_non_request_statuses():
    db = build_session()
    try:
        customer = create_customer(db)
        db.add(
            build_order(
                customer,
                status=OrderStatus.CONFIRMED.value,
                cancellation_requested_from=OrderStatus.CONFIRMED.value,
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_cancellation_requested_order_rejects_unsupported_original_status_value():
    db = build_session()
    try:
        customer = create_customer(db)
        db.add(
            build_order(
                customer,
                status=OrderStatus.CANCELLATION_REQUESTED.value,
                cancellation_requested_from="banana",
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()
    finally:
        db.close()


def test_order_item_snapshot_fields_do_not_change_when_product_changes():
    db = build_session()
    try:
        customer = create_customer(db)
        product = create_product(db, "Original catalog name")
        repository = OrderRepository(db)
        order = repository.create_order(
            build_order(customer),
            [build_order_item(product)],
        )
        item_id = order.items[0].id

        product.name = "Updated catalog name"
        product.description = "Updated catalog description"
        db.commit()

        stored_item = db.get(OrderItem, item_id)
        assert stored_item is not None
        assert stored_item.display_name == "Original catalog name"
        assert stored_item.customer_safe_description == "Catalog description"
        assert stored_item.provider_payload_snapshot["display_name"] == (
            "Original catalog name"
        )
        assert stored_item.product.name == "Updated catalog name"
    finally:
        db.close()
