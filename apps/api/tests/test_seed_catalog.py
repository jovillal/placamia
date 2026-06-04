import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

from app.core.database import Base
from app.models.category import Category
from app.models.product import Product
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def load_seed_catalog_module():
    """Load the root seed script as a test module.

    Returns:
        The imported seed_catalog module from the repository scripts directory.

    Side effects:
        Executes the module top-level constants and function definitions.
    """
    seed_script_path = Path(__file__).resolve().parents[3] / "scripts/seed_catalog.py"
    spec = importlib.util.spec_from_file_location("seed_catalog", seed_script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["seed_catalog"] = module
    spec.loader.exec_module(module)
    return module


def build_session():
    """Create an isolated in-memory database session for seed tests.

    Returns:
        A SQLAlchemy session bound to a fresh SQLite database.

    Side effects:
        Creates all application tables in the in-memory database.
    """
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


def test_seed_catalog_creates_mvp_categories_and_products():
    seed_catalog_module = load_seed_catalog_module()
    db = build_session()
    try:
        seed_catalog_module.seed_catalog(db)

        categories = db.execute(select(Category).order_by(Category.name)).scalars().all()
        products = db.execute(select(Product).order_by(Product.name)).scalars().all()

        assert [category.name for category in categories] == [
            "Evacuation",
            "Fire safety",
            "Obligation",
            "Prohibition",
            "Warning",
        ]
        assert len(products) == 10
        assert {product.name for product in products} == {
            "Assembly point sign",
            "Electrical hazard sign",
            "Emergency exit sign",
            "Evacuation route sign",
            "Fire extinguisher sign",
            "First aid kit sign",
            "No smoking sign",
            "Personal protective equipment sign",
            "Restricted area sign",
            "Waste sorting sign",
        }
        assert all(product.is_active for product in products)
        assert products[0].base_price == Decimal("22000.00")
    finally:
        db.close()


def test_seed_catalog_is_idempotent():
    seed_catalog_module = load_seed_catalog_module()
    db = build_session()
    try:
        seed_catalog_module.seed_catalog(db)
        seed_catalog_module.seed_catalog(db)

        category_count = db.execute(select(Category)).scalars().all()
        product_count = db.execute(select(Product)).scalars().all()

        assert len(category_count) == 5
        assert len(product_count) == 10
    finally:
        db.close()
