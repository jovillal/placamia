from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.category import Category
from app.models.kit import Kit
from app.models.kit_item import KitItem
from app.models.product import Product
from app.repositories.kit_repository import KitRepository
from app.services.kit_service import KitService


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


def test_kit_model_persists_catalog_bundle():
    db = build_session()
    try:
        kit = Kit(
            name="Emergency evacuation kit",
            description="Common signage for evacuation routes.",
        )
        db.add(kit)
        db.commit()
        db.refresh(kit)

        assert kit.id == 1
        assert kit.name == "Emergency evacuation kit"
        assert kit.description == "Common signage for evacuation routes."
        assert kit.is_active is True
        assert kit.created_at is not None
        assert kit.updated_at is not None
    finally:
        db.close()


def test_kit_item_model_links_kit_to_product_with_quantity():
    db = build_session()
    try:
        category = Category(name="Emergency", description=None)
        product = Product(
            name="Exit route sign",
            description=None,
            category=category,
            base_price=Decimal("12.50"),
        )
        kit = Kit(
            name="Emergency evacuation kit",
            description=None,
        )
        kit_item = KitItem(
            kit=kit,
            product=product,
            quantity=4,
        )
        db.add(kit_item)
        db.commit()
        db.refresh(kit)
        db.refresh(product)
        db.refresh(kit_item)

        assert kit_item.id == 1
        assert kit_item.kit_id == kit.id
        assert kit_item.product_id == product.id
        assert kit_item.quantity == 4
        assert kit_item.kit == kit
        assert kit_item.product == product
        assert kit.kit_items == [kit_item]
        assert product.kit_items == [kit_item]
        assert kit_item.created_at is not None
        assert kit_item.updated_at is not None
    finally:
        db.close()


def test_kit_and_kit_item_tables_match_mvp_fields():
    db = build_session()
    try:
        kit_columns = {
            column["name"] for column in inspect(db.bind).get_columns("kits")
        }
        kit_item_columns = {
            column["name"] for column in inspect(db.bind).get_columns("kit_items")
        }

        assert kit_columns == {
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        }
        assert kit_item_columns == {
            "id",
            "kit_id",
            "product_id",
            "quantity",
            "created_at",
            "updated_at",
        }
    finally:
        db.close()


def test_kit_repository_lists_active_kits_by_name():
    db = build_session()
    try:
        db.add_all(
            [
                Kit(
                    name="Warehouse safety kit",
                    description="Common warehouse safety signage.",
                ),
                Kit(
                    name="Emergency evacuation kit",
                    description=None,
                ),
            ]
        )
        db.commit()

        repository = KitRepository(db)

        kits = repository.get_active_kits()

        assert [kit.name for kit in kits] == [
            "Emergency evacuation kit",
            "Warehouse safety kit",
        ]
        assert all(kit.is_active for kit in kits)
    finally:
        db.close()


def test_kit_repository_excludes_inactive_kits():
    db = build_session()
    try:
        db.add_all(
            [
                Kit(
                    name="Active kit",
                    description=None,
                ),
                Kit(
                    name="Retired kit",
                    description="No longer shown to customers.",
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = KitRepository(db)

        kits = repository.get_active_kits()

        assert [kit.name for kit in kits] == ["Active kit"]
    finally:
        db.close()


def test_kit_service_lists_kits_from_repository():
    expected_kit = Kit(
        id=1,
        name="Emergency evacuation kit",
        description=None,
        is_active=True,
        created_at=datetime(2026, 5, 6, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, tzinfo=UTC),
    )

    class FakeKitRepository:
        def get_active_kits(self):
            return [expected_kit]

    service = KitService(FakeKitRepository())

    kits = service.list_kits()

    assert kits == [expected_kit]
