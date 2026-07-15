import asyncio
from datetime import UTC, datetime

import httpx
from app.core.database import Base, get_db
from app.main import app
from app.models.template import Template
from app.models.template_field import TemplateField
from app.repositories.template_repository import TemplateRepository
from app.services.template_service import TemplateService
from sqlalchemy import create_engine, inspect, select
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


async def request_templates(path: str = ""):
    """Call a public Template endpoint through the ASGI test transport."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(f"/api/v1/templates{path}")


def template_persistence_snapshot(db):
    """Return stored Template rows for read-only endpoint assertions."""
    return {
        table.name: db.execute(select(table).order_by(table.c.id)).all()
        for table in (Template.__table__, TemplateField.__table__)
    }


def test_template_model_persists_reusable_base_design():
    db = build_session()
    try:
        template = Template(
            name="Emergency exit template",
            description="Reusable base design for emergency exit signs.",
        )
        db.add(template)
        db.commit()
        db.refresh(template)

        assert template.id == 1
        assert template.name == "Emergency exit template"
        assert template.description == "Reusable base design for emergency exit signs."
        assert template.is_active is True
        assert template.created_at is not None
        assert template.updated_at is not None
    finally:
        db.close()


def test_template_model_table_matches_mvp_fields():
    db = build_session()
    try:
        columns = {
            column["name"] for column in inspect(db.bind).get_columns("templates")
        }

        assert columns == {
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        }
    finally:
        db.close()


def test_template_repository_lists_active_templates_by_name_and_id():
    db = build_session()
    try:
        db.add_all(
            [
                Template(
                    name="Warning sign template",
                    description="Reusable base warning sign design.",
                ),
                Template(
                    name="Emergency exit template",
                    description=None,
                ),
                Template(
                    name="Emergency exit template",
                    description="Second template with the same display name.",
                ),
                Template(
                    name="Retired template",
                    description="No longer available for new Designs.",
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = TemplateRepository(db)

        templates = repository.get_active_templates()

        assert [(template.name, template.id) for template in templates] == [
            ("Emergency exit template", 2),
            ("Emergency exit template", 3),
            ("Warning sign template", 1),
        ]
        assert all(template.is_active for template in templates)
    finally:
        db.close()


def test_template_repository_gets_active_template_by_id():
    db = build_session()
    try:
        db.add_all(
            [
                Template(
                    name="Emergency exit template",
                    description=None,
                ),
                Template(
                    name="Retired template",
                    description="No longer available for new Designs.",
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = TemplateRepository(db)

        active_template = repository.get_active_template_by_id(1)
        inactive_template = repository.get_active_template_by_id(2)
        missing_template = repository.get_active_template_by_id(999)

        assert active_template is not None
        assert active_template.name == "Emergency exit template"
        assert inactive_template is None
        assert missing_template is None
    finally:
        db.close()


def test_template_repository_gets_template_by_id_regardless_of_active_state():
    db = build_session()
    try:
        db.add_all(
            [
                Template(
                    name="Emergency exit template",
                    description=None,
                ),
                Template(
                    name="Retired template",
                    description="No longer available for new Designs.",
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = TemplateRepository(db)

        active_template = repository.get_template_by_id(1)
        inactive_template = repository.get_template_by_id(2)
        missing_template = repository.get_template_by_id(999)

        assert active_template is not None
        assert active_template.is_active is True
        assert inactive_template is not None
        assert inactive_template.is_active is False
        assert missing_template is None
    finally:
        db.close()


def test_template_service_lists_templates_from_repository():
    class FakeTemplateRepository:
        def get_active_templates(self):
            return [
                Template(
                    id=1,
                    name="Emergency exit template",
                    description=None,
                    is_active=True,
                    created_at=datetime(2026, 5, 4, tzinfo=UTC),
                    updated_at=datetime(2026, 5, 4, tzinfo=UTC),
                )
            ]

        def get_active_template_by_id(self, template_id):
            return None

    service = TemplateService(FakeTemplateRepository())

    templates = service.list_templates()

    assert len(templates) == 1
    assert templates[0].name == "Emergency exit template"


def test_template_service_gets_template_from_repository():
    expected_template = Template(
        id=1,
        name="Emergency exit template",
        description=None,
        is_active=True,
        created_at=datetime(2026, 5, 4, tzinfo=UTC),
        updated_at=datetime(2026, 5, 4, tzinfo=UTC),
    )

    class FakeTemplateRepository:
        def get_active_templates(self):
            return []

        def get_active_template_by_id(self, template_id):
            assert template_id == 1
            return expected_template

    service = TemplateService(FakeTemplateRepository())

    template = service.get_template(1)

    assert template == expected_template


def test_list_templates_endpoint_returns_exact_public_shape_without_authentication():
    db = build_session()
    active_template = Template(
        name="Emergency exit template",
        description="Reusable emergency exit sign design.",
    )
    duplicate_name_template = Template(
        name="Emergency exit template",
        description=None,
    )
    later_template = Template(
        name="Warning sign template",
        description=None,
    )
    inactive_template = Template(
        name="Retired template",
        description="Not public.",
        is_active=False,
    )
    db.add_all(
        [
            later_template,
            active_template,
            duplicate_name_template,
            inactive_template,
            TemplateField(
                template=active_template,
                field_name="legend",
                field_type="text",
                display_order=1,
            ),
        ]
    )
    db.commit()
    persistence_before = template_persistence_snapshot(db)

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = asyncio.run(request_templates())

        assert response.status_code == 200
        assert response.json() == {
            "data": [
                {
                    "id": active_template.id,
                    "name": "Emergency exit template",
                    "description": "Reusable emergency exit sign design.",
                },
                {
                    "id": duplicate_name_template.id,
                    "name": "Emergency exit template",
                    "description": None,
                },
                {
                    "id": later_template.id,
                    "name": "Warning sign template",
                    "description": None,
                },
            ]
        }
        assert template_persistence_snapshot(db) == persistence_before
        assert not db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_template_endpoint_returns_active_fields_in_stable_order():
    db = build_session()
    template = Template(
        name="Emergency exit template",
        description="Reusable emergency exit sign design.",
    )
    db.add_all(
        [
            TemplateField(
                template=template,
                field_name="material",
                field_type="select",
                is_required=True,
                allowed_values=["vinyl", "aluminum"],
                display_order=2,
            ),
            TemplateField(
                template=template,
                field_name="legend",
                field_type="text",
                is_required=True,
                allowed_values=None,
                display_order=1,
            ),
            TemplateField(
                template=template,
                field_name="reflective",
                field_type="boolean",
                is_required=False,
                allowed_values=None,
                display_order=1,
            ),
            TemplateField(
                template=template,
                field_name="retired_option",
                field_type="select",
                allowed_values=["retired"],
                display_order=0,
                is_active=False,
            ),
        ]
    )
    db.commit()
    persistence_before = template_persistence_snapshot(db)

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = asyncio.run(request_templates(f"/{template.id}"))

        assert response.status_code == 200
        assert response.json() == {
            "id": template.id,
            "name": "Emergency exit template",
            "description": "Reusable emergency exit sign design.",
            "fields": [
                {
                    "field_name": "legend",
                    "field_type": "text",
                    "is_required": True,
                    "allowed_values": None,
                    "display_order": 1,
                },
                {
                    "field_name": "reflective",
                    "field_type": "boolean",
                    "is_required": False,
                    "allowed_values": None,
                    "display_order": 1,
                },
                {
                    "field_name": "material",
                    "field_type": "select",
                    "is_required": True,
                    "allowed_values": ["vinyl", "aluminum"],
                    "display_order": 2,
                },
            ],
        }
        assert template_persistence_snapshot(db) == persistence_before
        assert not db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_template_endpoint_returns_empty_fields_without_fallbacks():
    db = build_session()
    template = Template(name="Plain template", description=None)
    db.add(
        TemplateField(
            template=template,
            field_name="retired_option",
            field_type="text",
            display_order=1,
            is_active=False,
        )
    )
    db.commit()

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        response = asyncio.run(request_templates(f"/{template.id}"))

        assert response.status_code == 200
        assert response.json() == {
            "id": template.id,
            "name": "Plain template",
            "description": None,
            "fields": [],
        }
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_template_endpoint_hides_inactive_and_unknown_templates_identically():
    db = build_session()
    inactive_template = Template(
        name="Retired template",
        description=None,
        is_active=False,
    )
    db.add(inactive_template)
    db.commit()

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        inactive_response = asyncio.run(request_templates(f"/{inactive_template.id}"))
        unknown_response = asyncio.run(request_templates("/999"))

        assert inactive_response.status_code == 404
        assert unknown_response.status_code == 404
        assert inactive_response.json() == {"detail": "Template not found"}
        assert unknown_response.json() == inactive_response.json()
    finally:
        app.dependency_overrides.clear()
        db.close()
