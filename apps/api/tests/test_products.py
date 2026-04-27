from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.category import Category
from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.services.product_service import ProductService


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


def test_product_model_links_to_category():
    db = build_session()
    try:
        category = Category(name="Warning", description="Warning signs")
        product = Product(
            name="Caution floor sign",
            description="Rigid caution sign",
            category=category,
            base_price=Decimal("19.99"),
        )
        db.add(product)
        db.commit()
        db.refresh(category)
        db.refresh(product)

        assert product.category.name == "Warning"
        assert category.products == [product]
        assert product.is_active is True
    finally:
        db.close()


def test_product_repository_lists_products_by_name_and_gets_by_id():
    db = build_session()
    try:
        category = Category(name="Emergency", description=None)
        db.add_all(
            [
                Product(
                    name="Exit route sign",
                    description=None,
                    category=category,
                    base_price=Decimal("12.50"),
                ),
                Product(
                    name="Assembly point sign",
                    description="Outdoor assembly point sign",
                    category=category,
                    base_price=Decimal("18.00"),
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = ProductRepository(db)

        products = repository.get_products()
        missing_product = repository.get_product_by_id(999)

        assert [product.name for product in products] == [
            "Assembly point sign",
            "Exit route sign",
        ]
        assert products[0].description == "Outdoor assembly point sign"
        assert products[0].base_price == Decimal("18.00")
        assert products[0].is_active is False
        assert repository.get_product_by_id(products[1].id).name == "Exit route sign"
        assert missing_product is None
    finally:
        db.close()


def test_product_service_lists_products_from_repository():
    class FakeProductRepository:
        def get_products(self):
            return [
                Product(
                    id=1,
                    name="Exit route sign",
                    description=None,
                    category_id=1,
                    base_price=Decimal("12.50"),
                    is_active=True,
                    created_at=datetime(2026, 4, 26, tzinfo=UTC),
                    updated_at=datetime(2026, 4, 26, tzinfo=UTC),
                )
            ]

        def get_product_by_id(self, product_id):
            return None

    service = ProductService(FakeProductRepository())

    products = service.list_products()

    assert len(products) == 1
    assert products[0].name == "Exit route sign"


def test_product_service_gets_product_from_repository():
    expected_product = Product(
        id=1,
        name="Exit route sign",
        description=None,
        category_id=1,
        base_price=Decimal("12.50"),
        is_active=True,
        created_at=datetime(2026, 4, 26, tzinfo=UTC),
        updated_at=datetime(2026, 4, 26, tzinfo=UTC),
    )

    class FakeProductRepository:
        def get_products(self):
            return []

        def get_product_by_id(self, product_id):
            assert product_id == 1
            return expected_product

    service = ProductService(FakeProductRepository())

    product = service.get_product(1)

    assert product == expected_product
