from datetime import UTC, datetime

from app.core.database import Base
from app.models.template import Template
from app.repositories.template_repository import TemplateRepository
from app.services.template_service import TemplateService
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
        columns = {column["name"] for column in inspect(db.bind).get_columns("templates")}

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


def test_template_repository_lists_active_templates_by_name():
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
                    name="Retired template",
                    description="No longer available for new Designs.",
                    is_active=False,
                ),
            ]
        )
        db.commit()

        repository = TemplateRepository(db)

        templates = repository.get_active_templates()

        assert [template.name for template in templates] == [
            "Emergency exit template",
            "Warning sign template",
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
