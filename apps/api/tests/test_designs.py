from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import Base
from app.models.category import Category
from app.models.design import Design
from app.models.product import Product
from app.models.template import Template
from app.models.user import User
from app.repositories.design_repository import DesignRepository
from app.services.design_validation_service import DesignValidationError
from app.services.design_service import DesignService
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


def seed_user(db, email: str = "designer@example.com") -> User:
    """Persist one customer for Design ownership tests."""
    user = User(email=email, full_name="Test Designer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_product(db) -> Product:
    """Persist one Product used as the Design Template pricing anchor."""
    product = Product(
        name="Configurable safety sign",
        description=None,
        category=Category(name=f"Safety signs {id(db)}", description=None),
        base_price=Decimal("20.00"),
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def test_design_model_persists_customization_values_for_template():
    db = build_session()
    try:
        customer = seed_user(db)
        product = seed_product(db)
        template = Template(
            product=product,
            name="Emergency exit template",
            description=None,
        )
        design = Design(
            customer=customer,
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
        assert design.customer_id == customer.id
        assert design.customer == customer
        assert customer.designs == [design]
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
            "customer_id",
            "template_id",
            "customization_values",
            "created_at",
            "updated_at",
        }
        foreign_keys = inspect(db.bind).get_foreign_keys("designs")
        indexes = inspect(db.bind).get_indexes("designs")

        assert any(
            foreign_key["constrained_columns"] == ["customer_id"]
            and foreign_key["referred_table"] == "users"
            for foreign_key in foreign_keys
        )
        assert any(index["column_names"] == ["customer_id"] for index in indexes)
    finally:
        db.close()


def test_design_repository_persists_design_records():
    db = build_session()
    try:
        customer = seed_user(db)
        product = seed_product(db)
        template = Template(
            product=product,
            name="Warning sign template",
            description=None,
        )
        db.add(template)
        db.commit()
        db.refresh(template)

        repository = DesignRepository(db)

        design = repository.create_design(
            customer_id=customer.id,
            template_id=template.id,
            customization_values={
                "legend": "High voltage",
                "material": "aluminum",
            },
        )

        assert design.id == 1
        assert design.customer_id == customer.id
        assert design.template_id == template.id
        assert design.customization_values == {
            "legend": "High voltage",
            "material": "aluminum",
        }
        assert design.created_at is not None
        assert design.updated_at is not None
    finally:
        db.close()


def test_design_repository_retrieves_design_only_for_owner():
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        other_customer = seed_user(db, "other@example.com")
        product = seed_product(db)
        template = Template(
            product=product,
            name="Fire extinguisher template",
            description=None,
        )
        design = Design(
            customer=owner,
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

        stored_design = repository.get_design_for_customer(design.id, owner.id)
        cross_customer_design = repository.get_design_for_customer(
            design.id,
            other_customer.id,
        )
        missing_design = repository.get_design_for_customer(999, owner.id)

        assert stored_design == design
        assert stored_design.template == template
        assert cross_customer_design is None
        assert missing_design is None
    finally:
        db.close()


def test_design_repository_preserves_template_relationship():
    db = build_session()
    try:
        customer = seed_user(db)
        product = seed_product(db)
        template = Template(
            product=product,
            name="Mandatory PPE template",
            description=None,
        )
        db.add(template)
        db.commit()
        db.refresh(template)

        repository = DesignRepository(db)

        design = repository.create_design(
            customer_id=customer.id,
            template_id=template.id,
            customization_values={"legend": "Use eye protection"},
        )
        stored_design = repository.get_design_for_customer(design.id, customer.id)

        assert stored_design is not None
        assert stored_design.template == template
        assert stored_design in template.designs
    finally:
        db.close()


def test_design_service_validates_before_persisting_backend_owned_design():
    expected_design = Design(
        id=1,
        customer_id=7,
        template_id=1,
        customization_values={"legend": "Emergency exit"},
        created_at=datetime(2026, 5, 11, tzinfo=UTC),
        updated_at=datetime(2026, 5, 11, tzinfo=UTC),
    )

    calls: list[str] = []

    class FakeSession:
        def commit(self):
            calls.append("commit")

        def rollback(self):
            calls.append("rollback")

    class FakeValidationService:
        def validate_customization(self, template_id, customization_values):
            calls.append("validate")
            assert template_id == 1
            assert customization_values == {"legend": "Emergency exit"}
            return {"legend": "Emergency exit"}

    class FakeDesignRepository:
        def create_design(self, customer_id, template_id, customization_values):
            calls.append("persist")
            assert customer_id == 7
            assert template_id == 1
            assert customization_values == {"legend": "Emergency exit"}
            return expected_design

        def get_design_for_customer(self, design_id, customer_id):
            return None

    service = DesignService(
        FakeDesignRepository(),
        FakeValidationService(),
        FakeSession(),
    )

    design = service.create_design(
        customer_id=7,
        template_id=1,
        customization_values={"legend": "Emergency exit"},
    )

    assert design == expected_design
    assert calls == ["validate", "persist", "commit"]


def test_design_service_does_not_persist_rejected_customization():
    calls: list[str] = []

    class FakeSession:
        def commit(self):
            calls.append("commit")

        def rollback(self):
            calls.append("rollback")

    class RejectingValidationService:
        def validate_customization(self, template_id, customization_values):
            calls.append("validate")
            raise DesignValidationError(
                code="missing_required_field",
                message="Customization is missing required TemplateFields.",
            )

    class FakeDesignRepository:
        def create_design(self, customer_id, template_id, customization_values):
            raise AssertionError("Rejected customization must not be persisted")

        def get_design_for_customer(self, design_id, customer_id):
            return None

    service = DesignService(
        FakeDesignRepository(),
        RejectingValidationService(),
        FakeSession(),
    )

    try:
        service.create_design(
            customer_id=7,
            template_id=1,
            customization_values={},
        )
    except DesignValidationError as exc:
        assert exc.code == "missing_required_field"
    else:
        raise AssertionError("Expected DesignValidationError")

    assert calls == ["validate"]


@pytest.mark.parametrize("failure_stage", ["persist", "commit"])
def test_design_service_rolls_back_persistence_or_commit_failure(failure_stage):
    calls: list[str] = []

    class FakeSession:
        def commit(self):
            calls.append("commit")
            if failure_stage == "commit":
                raise RuntimeError("commit failed")

        def rollback(self):
            calls.append("rollback")

    class FakeValidationService:
        def validate_customization(self, template_id, customization_values):
            calls.append("validate")
            return customization_values

    class FakeDesignRepository:
        def create_design(self, customer_id, template_id, customization_values):
            calls.append("persist")
            if failure_stage == "persist":
                raise RuntimeError("persist failed")
            return Design(
                customer_id=customer_id,
                template_id=template_id,
                customization_values=customization_values,
            )

        def get_design_for_customer(self, design_id, customer_id):
            return None

    service = DesignService(
        FakeDesignRepository(),
        FakeValidationService(),
        FakeSession(),
    )

    with pytest.raises(RuntimeError, match=f"{failure_stage} failed"):
        service.create_design(
            customer_id=7,
            template_id=1,
            customization_values={"legend": "Emergency exit"},
        )

    expected_calls = ["validate", "persist"]
    if failure_stage == "commit":
        expected_calls.append("commit")
    expected_calls.append("rollback")
    assert calls == expected_calls


def test_design_service_rolls_back_a_staged_design_after_repository_failure():
    db = build_session()
    try:
        customer = seed_user(db)
        template = Template(
            product=seed_product(db),
            name="Emergency exit template",
            description=None,
        )
        db.add(template)
        db.commit()
        db.refresh(template)

        class FakeValidationService:
            def validate_customization(self, template_id, customization_values):
                return customization_values

        class FailingDesignRepository:
            def create_design(self, customer_id, template_id, customization_values):
                db.add(
                    Design(
                        customer_id=customer_id,
                        template_id=template_id,
                        customization_values=customization_values,
                    )
                )
                db.flush()
                raise RuntimeError("persistence failed after flush")

            def get_design_for_customer(self, design_id, customer_id):
                return None

        service = DesignService(
            FailingDesignRepository(),
            FakeValidationService(),
            db,
        )

        with pytest.raises(RuntimeError, match="persistence failed after flush"):
            service.create_design(
                customer_id=customer.id,
                template_id=template.id,
                customization_values={"legend": "Emergency exit"},
            )

        assert db.scalar(select(Design)) is None
        assert not db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        db.close()


def test_design_service_delegates_owner_scoped_retrieval_to_repository():
    expected_design = Design(
        id=1,
        customer_id=7,
        template_id=1,
        customization_values={"legend": "Emergency exit"},
        created_at=datetime(2026, 5, 11, tzinfo=UTC),
        updated_at=datetime(2026, 5, 11, tzinfo=UTC),
    )

    class FakeDesignRepository:
        def create_design(self, customer_id, template_id, customization_values):
            return None

        def get_design_for_customer(self, design_id, customer_id):
            assert design_id == 1
            assert customer_id == 7
            return expected_design

    class FakeValidationService:
        pass

    service = DesignService(
        FakeDesignRepository(),
        FakeValidationService(),
        object(),
    )

    design = service.get_design_for_customer(1, 7)

    assert design == expected_design
