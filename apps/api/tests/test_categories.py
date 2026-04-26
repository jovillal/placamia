from datetime import UTC, datetime
import asyncio

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.category import Category
from app.repositories.category_repository import CategoryRepository
from app.services.category_service import CategoryService


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


def test_category_repository_lists_categories_by_name():
    db = build_session()
    try:
        db.add_all(
            [
                Category(name="Warning", description="Warning signs"),
                Category(name="Emergency", description=None),
            ]
        )
        db.commit()

        repository = CategoryRepository(db)

        categories = repository.list_categories()

        assert [category.name for category in categories] == ["Emergency", "Warning"]
        assert categories[0].description is None
    finally:
        db.close()


def test_category_service_lists_categories_from_repository():
    class FakeCategoryRepository:
        def list_categories(self):
            return [
                Category(
                    id=1,
                    name="Emergency",
                    description=None,
                    created_at=datetime(2026, 4, 18, tzinfo=UTC),
                    updated_at=datetime(2026, 4, 18, tzinfo=UTC),
                )
            ]

    service = CategoryService(FakeCategoryRepository())

    categories = service.list_categories()

    assert len(categories) == 1
    assert categories[0].name == "Emergency"


def test_list_categories_endpoint_returns_catalog_categories():
    db = build_session()
    db.add_all(
        [
            Category(name="Warning", description="Warning signs"),
            Category(name="Emergency", description=None),
        ]
    )
    db.commit()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    try:

        async def get_categories():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/catalog/categories")

        response = asyncio.run(get_categories())

        assert response.status_code == 200
        assert response.json()["data"] == [
            {
                "id": 2,
                "name": "Emergency",
                "description": None,
                "created_at": response.json()["data"][0]["created_at"],
                "updated_at": response.json()["data"][0]["updated_at"],
            },
            {
                "id": 1,
                "name": "Warning",
                "description": "Warning signs",
                "created_at": response.json()["data"][1]["created_at"],
                "updated_at": response.json()["data"][1]["updated_at"],
            },
        ]
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_list_categories_endpoint_is_documented_in_openapi():
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
    operation = schema["paths"]["/api/v1/catalog/categories"]["get"]
    assert operation["summary"] == "List catalog categories"
    assert "200" in operation["responses"]
