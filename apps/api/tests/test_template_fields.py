from datetime import UTC, datetime

from app.core.database import Base
from app.models.template import Template
from app.models.template_field import TemplateField
from app.repositories.template_field_repository import TemplateFieldRepository
from app.services.template_field_service import TemplateFieldService
from sqlalchemy import create_engine, inspect
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


def test_template_field_model_persists_customization_definition():
    db = build_session()
    try:
        template = Template(
            name="Emergency exit template",
            description=None,
        )
        field = TemplateField(
            template=template,
            field_name="material",
            field_type="select",
            is_required=True,
            allowed_values=["vinyl", "aluminum"],
            display_order=2,
        )
        db.add(field)
        db.commit()
        db.refresh(template)
        db.refresh(field)

        assert field.id == 1
        assert field.template_id == template.id
        assert field.template == template
        assert template.template_fields == [field]
        assert field.field_name == "material"
        assert field.field_type == "select"
        assert field.is_required is True
        assert field.allowed_values == ["vinyl", "aluminum"]
        assert field.display_order == 2
        assert field.is_active is True
        assert field.created_at is not None
        assert field.updated_at is not None
    finally:
        db.close()


def test_template_field_model_table_matches_mvp_fields():
    db = build_session()
    try:
        columns = {
            column["name"] for column in inspect(db.bind).get_columns("template_fields")
        }

        assert columns == {
            "id",
            "template_id",
            "field_name",
            "field_type",
            "is_required",
            "allowed_values",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        }
    finally:
        db.close()


def test_template_field_repository_lists_active_fields_by_display_order_and_id():
    db = build_session()
    try:
        template = Template(
            name="Emergency exit template",
            description=None,
        )
        other_template = Template(
            name="Warning template",
            description=None,
        )
        db.add_all(
            [
                TemplateField(
                    template=template,
                    field_name="size",
                    field_type="select",
                    allowed_values=["small", "large"],
                    display_order=2,
                ),
                TemplateField(
                    template=template,
                    field_name="text",
                    field_type="text",
                    is_required=True,
                    allowed_values=None,
                    display_order=1,
                ),
                TemplateField(
                    template=template,
                    field_name="reflective",
                    field_type="boolean",
                    allowed_values=None,
                    display_order=1,
                ),
                TemplateField(
                    template=template,
                    field_name="retired_option",
                    field_type="select",
                    allowed_values=["retired"],
                    display_order=3,
                    is_active=False,
                ),
                TemplateField(
                    template=other_template,
                    field_name="other_template_text",
                    field_type="text",
                    display_order=1,
                ),
            ]
        )
        db.commit()

        repository = TemplateFieldRepository(db)

        fields = repository.get_active_fields_for_template(template.id)

        assert [field.field_name for field in fields] == [
            "text",
            "reflective",
            "size",
        ]
        assert all(field.is_active for field in fields)
        assert {field.template_id for field in fields} == {template.id}
    finally:
        db.close()


def test_template_field_repository_returns_empty_for_inactive_or_missing_template():
    db = build_session()
    try:
        inactive_template = Template(
            name="Retired template",
            description=None,
            is_active=False,
        )
        db.add(
            TemplateField(
                template=inactive_template,
                field_name="material",
                field_type="select",
                allowed_values=["vinyl"],
                display_order=1,
            )
        )
        db.commit()

        repository = TemplateFieldRepository(db)

        inactive_fields = repository.get_active_fields_for_template(
            inactive_template.id
        )
        missing_fields = repository.get_active_fields_for_template(999)

        assert inactive_fields == []
        assert missing_fields == []
    finally:
        db.close()


def test_template_field_service_lists_fields_from_repository():
    expected_field = TemplateField(
        id=1,
        template_id=1,
        field_name="material",
        field_type="select",
        is_required=True,
        allowed_values=["vinyl", "aluminum"],
        display_order=1,
        is_active=True,
        created_at=datetime(2026, 5, 4, tzinfo=UTC),
        updated_at=datetime(2026, 5, 4, tzinfo=UTC),
    )

    class FakeTemplateFieldRepository:
        def get_active_fields_for_template(self, template_id):
            assert template_id == 1
            return [expected_field]

    service = TemplateFieldService(FakeTemplateFieldRepository())

    fields = service.list_fields_for_template(1)

    assert fields == [expected_field]
