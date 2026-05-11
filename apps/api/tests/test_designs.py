from datetime import UTC, datetime

from app.core.database import Base
from app.models.design import Design
from app.models.template import Template
from app.repositories.design_repository import DesignRepository
from app.services.design_service import DesignService
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


def test_design_model_persists_customization_values_for_template():
    db = build_session()
    try:
        template = Template(
            name="Emergency exit template",
            description=None,
        )
        design = Design(
            template=template,
            customization_values={
                "legend": "Emergency exit",
                "material": "vinyl",
                "width_cm": 30,
                "reflective": True,
            },
        )
        db.add(design)
        db.commit()
        db.refresh(template)
        db.refresh(design)

        assert design.id == 1
        assert design.template_id == template.id
        assert design.template == template
        assert template.designs == [design]
        assert design.customization_values == {
            "legend": "Emergency exit",
            "material": "vinyl",
            "width_cm": 30,
            "reflective": True,
        }
        assert design.created_at is not None
        assert design.updated_at is not None
    finally:
        db.close()


def test_design_model_table_matches_mvp_fields():
    db = build_session()
    try:
        columns = {column["name"] for column in inspect(db.bind).get_columns("designs")}

        assert columns == {
            "id",
            "template_id",
            "customization_values",
            "created_at",
            "updated_at",
        }
    finally:
        db.close()


def test_design_repository_persists_design_records():
    db = build_session()
    try:
        template = Template(
            name="Warning sign template",
            description=None,
        )
        db.add(template)
        db.commit()
        db.refresh(template)

        repository = DesignRepository(db)

        design = repository.create_design(
            template_id=template.id,
            customization_values={
                "legend": "High voltage",
                "material": "aluminum",
            },
        )

        assert design.id == 1
        assert design.template_id == template.id
        assert design.customization_values == {
            "legend": "High voltage",
            "material": "aluminum",
        }
        assert design.created_at is not None
        assert design.updated_at is not None
    finally:
        db.close()


def test_design_repository_retrieves_design_by_id():
    db = build_session()
    try:
        template = Template(
            name="Fire extinguisher template",
            description=None,
        )
        design = Design(
            template=template,
            customization_values={
                "legend": "Fire extinguisher",
                "reflective": False,
            },
        )
        db.add(design)
        db.commit()
        db.refresh(design)

        repository = DesignRepository(db)

        stored_design = repository.get_design_by_id(design.id)
        missing_design = repository.get_design_by_id(999)

        assert stored_design == design
        assert stored_design.template == template
        assert missing_design is None
    finally:
        db.close()


def test_design_repository_preserves_template_relationship():
    db = build_session()
    try:
        template = Template(
            name="Mandatory PPE template",
            description=None,
        )
        db.add(template)
        db.commit()
        db.refresh(template)

        repository = DesignRepository(db)

        design = repository.create_design(
            template_id=template.id,
            customization_values={"legend": "Use eye protection"},
        )
        stored_design = repository.get_design_by_id(design.id)

        assert stored_design is not None
        assert stored_design.template == template
        assert stored_design in template.designs
    finally:
        db.close()


def test_design_service_delegates_persistence_to_repository():
    expected_design = Design(
        id=1,
        template_id=1,
        customization_values={"legend": "Emergency exit"},
        created_at=datetime(2026, 5, 11, tzinfo=UTC),
        updated_at=datetime(2026, 5, 11, tzinfo=UTC),
    )

    class FakeDesignRepository:
        def create_design(self, template_id, customization_values):
            assert template_id == 1
            assert customization_values == {"legend": "Emergency exit"}
            return expected_design

        def get_design_by_id(self, design_id):
            return None

    service = DesignService(FakeDesignRepository())

    design = service.create_design(
        template_id=1,
        customization_values={"legend": "Emergency exit"},
    )

    assert design == expected_design


def test_design_service_delegates_retrieval_to_repository():
    expected_design = Design(
        id=1,
        template_id=1,
        customization_values={"legend": "Emergency exit"},
        created_at=datetime(2026, 5, 11, tzinfo=UTC),
        updated_at=datetime(2026, 5, 11, tzinfo=UTC),
    )

    class FakeDesignRepository:
        def create_design(self, template_id, customization_values):
            return None

        def get_design_by_id(self, design_id):
            assert design_id == 1
            return expected_design

    service = DesignService(FakeDesignRepository())

    design = service.get_design(1)

    assert design == expected_design
