"""Seed the initial MVP catalog categories and products.

This script is intended for local development and test environments. It uses
the SQLAlchemy application models directly, inserts the initial catalog data
from the MVP product document, and can be run repeatedly without duplicating
records.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.category import Category
from app.models.product import Product


@dataclass(frozen=True)
class CategorySeed:
    """Catalog category seed data.

    Args:
        name: Customer-facing category name.
        description: Short explanation of the category purpose.
    """

    name: str
    description: str


@dataclass(frozen=True)
class ProductSeed:
    """Catalog product seed data.

    Args:
        name: Customer-facing product name.
        description: Short explanation of the product use case.
        category_name: Name of the category that owns the product.
        base_price: Starting unit price in COP before dynamic pricing rules.
    """

    name: str
    description: str
    category_name: str
    base_price: Decimal


CATEGORY_SEEDS: tuple[CategorySeed, ...] = (
    CategorySeed(
        name="Evacuation",
        description="Signs for emergency exits, routes, and meeting points.",
    ),
    CategorySeed(
        name="Fire safety",
        description="Signs for fire extinguishers and emergency equipment.",
    ),
    CategorySeed(
        name="Warning",
        description="Signs for electrical hazards and other risk conditions.",
    ),
    CategorySeed(
        name="Prohibition",
        description="Signs for restricted actions and smoke-free spaces.",
    ),
    CategorySeed(
        name="Obligation",
        description="Signs for required personal protective equipment.",
    ),
)


PRODUCT_SEEDS: tuple[ProductSeed, ...] = (
    ProductSeed(
        name="Emergency exit sign",
        description="Standard sign for marking emergency exits.",
        category_name="Evacuation",
        base_price=Decimal("18000.00"),
    ),
    ProductSeed(
        name="Evacuation route sign",
        description="Directional arrow sign for evacuation routes.",
        category_name="Evacuation",
        base_price=Decimal("18000.00"),
    ),
    ProductSeed(
        name="Assembly point sign",
        description="Sign for identifying outdoor or indoor meeting points.",
        category_name="Evacuation",
        base_price=Decimal("22000.00"),
    ),
    ProductSeed(
        name="Fire extinguisher sign",
        description="Sign for locating fire extinguishers quickly.",
        category_name="Fire safety",
        base_price=Decimal("18000.00"),
    ),
    ProductSeed(
        name="First aid kit sign",
        description="Sign for identifying first aid kit locations.",
        category_name="Fire safety",
        base_price=Decimal("18000.00"),
    ),
    ProductSeed(
        name="Electrical hazard sign",
        description="Warning sign for areas with electrical risk.",
        category_name="Warning",
        base_price=Decimal("20000.00"),
    ),
    ProductSeed(
        name="Waste sorting sign",
        description="Sign for waste separation and disposal areas.",
        category_name="Warning",
        base_price=Decimal("20000.00"),
    ),
    ProductSeed(
        name="Restricted area sign",
        description="Sign for areas with limited or authorized access.",
        category_name="Prohibition",
        base_price=Decimal("18000.00"),
    ),
    ProductSeed(
        name="No smoking sign",
        description="Smoke-free environment and no-smoking sign.",
        category_name="Prohibition",
        base_price=Decimal("18000.00"),
    ),
    ProductSeed(
        name="Personal protective equipment sign",
        description="Mandatory PPE sign for work areas.",
        category_name="Obligation",
        base_price=Decimal("20000.00"),
    ),
)


def seed_categories(db: Session) -> dict[str, Category]:
    """Create or update MVP catalog categories.

    Args:
        db: SQLAlchemy session used to read and write category records.

    Returns:
        A mapping of category name to persisted category model.

    Side effects:
        Adds missing category rows and updates descriptions for existing rows.
    """
    category_names = [seed.name for seed in CATEGORY_SEEDS]
    result = db.execute(select(Category).where(Category.name.in_(category_names)))
    categories_by_name = {category.name: category for category in result.scalars()}

    for seed in CATEGORY_SEEDS:
        category = categories_by_name.get(seed.name)
        if category is None:
            category = Category(name=seed.name, description=seed.description)
            db.add(category)
            categories_by_name[seed.name] = category
        else:
            category.description = seed.description

    db.flush()
    return categories_by_name


def seed_products(db: Session, categories_by_name: dict[str, Category]) -> None:
    """Create or update MVP catalog products.

    Args:
        db: SQLAlchemy session used to read and write product records.
        categories_by_name: Persisted categories keyed by category name.

    Returns:
        None.

    Side effects:
        Adds missing product rows and updates seed-managed product fields.
    """
    product_names = [seed.name for seed in PRODUCT_SEEDS]
    result = db.execute(select(Product).where(Product.name.in_(product_names)))
    products_by_name = {product.name: product for product in result.scalars()}

    for seed in PRODUCT_SEEDS:
        product = products_by_name.get(seed.name)
        category = categories_by_name[seed.category_name]
        if product is None:
            db.add(
                Product(
                    name=seed.name,
                    description=seed.description,
                    category=category,
                    base_price=seed.base_price,
                    is_active=True,
                )
            )
        else:
            product.description = seed.description
            product.category = category
            product.base_price = seed.base_price
            product.is_active = True


def seed_catalog(db: Session) -> None:
    """Seed all initial MVP catalog records in one transaction.

    Args:
        db: SQLAlchemy session used to persist seed records.

    Returns:
        None.

    Side effects:
        Commits category and product seed data to the connected database.
    """
    categories_by_name = seed_categories(db)
    seed_products(db, categories_by_name)
    db.commit()


def main() -> None:
    """Run the catalog seed script against the configured database.

    Args:
        None.

    Returns:
        None.

    Side effects:
        Opens a database session, writes seed data, and closes the session.
    """
    if SessionLocal.kw["bind"] is None:
        raise RuntimeError("DATABASE_URL is not configured")

    db = SessionLocal()
    try:
        seed_catalog(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
