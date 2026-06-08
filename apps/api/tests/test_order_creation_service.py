from decimal import Decimal

from app.core.database import Base
from app.models.category import Category
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.schemas.checkout import ValidatedCheckoutState
from app.schemas.order import OrderCreateRequest
from app.services.checkout_service import DEFAULT_TERMS_POLICY_VERSION
from app.services.order_creation_service import OrderCreationService
from app.services.pricing_service import PricingItemType
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated in-memory database session for order service tests."""
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


def seed_user(db) -> User:
    """Persist one customer for draft order service tests."""
    user = User(email="buyer@example.com", full_name="Test Buyer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_product(db) -> Product:
    """Persist one product used only as a foreign-key target."""
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


class CheckoutServiceStub:
    """Return a pre-captured checkout state without loading catalog data."""

    def __init__(self, checkout_state: ValidatedCheckoutState) -> None:
        """Store the checkout state returned to the order service."""
        self.checkout_state = checkout_state

    def validate_checkout(self, request: OrderCreateRequest) -> ValidatedCheckoutState:
        """Return the stored checkout state for the supplied order request."""
        return self.checkout_state


def order_request(product: Product) -> OrderCreateRequest:
    """Build a minimal authenticated draft order request."""
    return OrderCreateRequest(
        item_type=PricingItemType.PRODUCT,
        item_id=product.id,
        quantity=2,
        terms_acknowledgement={
            "accepted": True,
            "policy_version": DEFAULT_TERMS_POLICY_VERSION,
        },
    )


def checkout_state(product: Product) -> ValidatedCheckoutState:
    """Build checkout state with metadata captured before catalog changes."""
    return ValidatedCheckoutState(
        item_type=PricingItemType.PRODUCT,
        item_id=product.id,
        product_id=product.id,
        display_name="Checkout-captured product name",
        customer_safe_description="Checkout-captured description",
        quantity=2,
        selected_options={},
        currency="COP",
        customer_unit_price=Decimal("20.00"),
        customer_subtotal=Decimal("40.00"),
        preview_total=Decimal("40.00"),
        pricing_rule="temporary_product_base_price_v1",
        provider_quote_reference=f"local-quote-product-{product.id}",
        assigned_provider_id="local-provider",
        terms_policy_version=DEFAULT_TERMS_POLICY_VERSION,
    )


def test_order_creation_uses_validated_checkout_snapshot_after_catalog_changes():
    db = build_session()
    try:
        user = seed_user(db)
        product = seed_product(db)
        captured_state = checkout_state(product)
        product.name = "Changed catalog name"
        product.description = "Changed catalog description"
        db.commit()
        service = OrderCreationService(
            CheckoutServiceStub(captured_state),
            OrderRepository(db),
        )

        order = service.create_draft_order(order_request(product), user)

        item = db.get(OrderItem, order.items[0].id)
        assert item is not None
        assert item.display_name == "Checkout-captured product name"
        assert item.customer_safe_description == "Checkout-captured description"
        assert item.provider_payload_snapshot["display_name"] == (
            "Checkout-captured product name"
        )
        assert item.product.name == "Changed catalog name"
    finally:
        db.close()
