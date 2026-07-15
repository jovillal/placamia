from decimal import Decimal

import pytest
from app.core.database import Base
from app.models.category import Category
from app.models.design import Design
from app.models.product import Product
from app.models.template import Template
from app.models.template_field import TemplateField
from app.models.user import User
from app.repositories.design_repository import DesignRepository
from app.repositories.template_field_repository import TemplateFieldRepository
from app.repositories.template_repository import TemplateRepository
from app.services.design_validation_service import (
    DesignValidationError,
    DesignValidationService,
)
from sqlalchemy import create_engine, func, select
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
    return product


def build_validation_service(db):
    return DesignValidationService(
        template_repository=TemplateRepository(db),
        template_field_repository=TemplateFieldRepository(db),
    )


def add_template_with_mvp_fields(db, *, is_active=True):
    product = seed_product(db)
    template = Template(
        product=product,
        name="Emergency exit template",
        description=None,
        is_active=is_active,
    )
    db.add_all(
        [
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
                field_name="material",
                field_type="select",
                is_required=True,
                allowed_values=["vinyl", "aluminum"],
                display_order=2,
            ),
            TemplateField(
                template=template,
                field_name="width_cm",
                field_type="number",
                is_required=True,
                allowed_values=None,
                display_order=3,
            ),
            TemplateField(
                template=template,
                field_name="reflective",
                field_type="boolean",
                is_required=False,
                allowed_values=None,
                display_order=4,
            ),
        ]
    )
    db.commit()
    db.refresh(template)
    return template


def design_count(db):
    return db.scalar(select(func.count()).select_from(Design))


def assert_validation_error(error_info, code):
    assert error_info.value.code == code


def test_design_validation_accepts_valid_mvp_customization_payload():
    db = build_session()
    try:
        template = add_template_with_mvp_fields(db)
        service = build_validation_service(db)

        accepted_values = service.validate_customization(
            template_id=template.id,
            customization_values={
                "legend": "Emergency exit",
                "material": "vinyl",
                "width_cm": 30,
                "reflective": True,
            },
        )

        assert accepted_values == {
            "legend": "Emergency exit",
            "material": "vinyl",
            "width_cm": 30,
            "reflective": True,
        }
        assert design_count(db) == 0
    finally:
        db.close()


def test_design_validation_rejects_missing_template():
    db = build_session()
    try:
        service = build_validation_service(db)

        with pytest.raises(DesignValidationError) as error_info:
            service.validate_customization(
                template_id=999,
                customization_values={"legend": "Emergency exit"},
            )

        assert_validation_error(error_info, "template_not_found")
        assert design_count(db) == 0
    finally:
        db.close()


def test_design_validation_rejects_inactive_template():
    db = build_session()
    try:
        template = add_template_with_mvp_fields(db, is_active=False)
        service = build_validation_service(db)

        with pytest.raises(DesignValidationError) as error_info:
            service.validate_customization(
                template_id=template.id,
                customization_values={
                    "legend": "Emergency exit",
                    "material": "vinyl",
                    "width_cm": 30,
                },
            )

        assert_validation_error(error_info, "template_inactive")
        assert design_count(db) == 0
    finally:
        db.close()


def test_design_validation_rejects_unknown_template_field():
    db = build_session()
    try:
        template = add_template_with_mvp_fields(db)
        service = build_validation_service(db)

        with pytest.raises(DesignValidationError) as error_info:
            service.validate_customization(
                template_id=template.id,
                customization_values={
                    "legend": "Emergency exit",
                    "material": "vinyl",
                    "width_cm": 30,
                    "frontend_price": 19.99,
                },
            )

        assert_validation_error(error_info, "unknown_template_field")
        assert design_count(db) == 0
    finally:
        db.close()


def test_design_validation_rejects_missing_required_field():
    db = build_session()
    try:
        template = add_template_with_mvp_fields(db)
        service = build_validation_service(db)

        with pytest.raises(DesignValidationError) as error_info:
            service.validate_customization(
                template_id=template.id,
                customization_values={
                    "legend": "Emergency exit",
                    "width_cm": 30,
                },
            )

        assert_validation_error(error_info, "missing_required_field")
        assert design_count(db) == 0
    finally:
        db.close()


def test_design_validation_rejects_unsupported_field_type():
    db = build_session()
    try:
        template = Template(
            product=seed_product(db),
            name="Warning template",
            description=None,
        )
        db.add(
            TemplateField(
                template=template,
                field_name="color",
                field_type="color",
                is_required=True,
                allowed_values=None,
                display_order=1,
            )
        )
        db.commit()
        db.refresh(template)
        service = build_validation_service(db)

        with pytest.raises(DesignValidationError) as error_info:
            service.validate_customization(
                template_id=template.id,
                customization_values={"color": "red"},
            )

        assert_validation_error(error_info, "unsupported_field_type")
        assert design_count(db) == 0
    finally:
        db.close()


def test_design_validation_rejects_invalid_select_value():
    db = build_session()
    try:
        template = add_template_with_mvp_fields(db)
        service = build_validation_service(db)

        with pytest.raises(DesignValidationError) as error_info:
            service.validate_customization(
                template_id=template.id,
                customization_values={
                    "legend": "Emergency exit",
                    "material": "paper",
                    "width_cm": 30,
                },
            )

        assert_validation_error(error_info, "invalid_select_value")
        assert design_count(db) == 0
    finally:
        db.close()


def test_design_validation_rejects_invalid_submitted_value_type():
    db = build_session()
    try:
        template = add_template_with_mvp_fields(db)
        service = build_validation_service(db)

        with pytest.raises(DesignValidationError) as error_info:
            service.validate_customization(
                template_id=template.id,
                customization_values={
                    "legend": "Emergency exit",
                    "material": "vinyl",
                    "width_cm": "30",
                },
            )

        assert_validation_error(error_info, "invalid_value_type")
        assert design_count(db) == 0
    finally:
        db.close()


def test_design_validation_rejected_payload_does_not_persist_design_data():
    db = build_session()
    try:
        template = add_template_with_mvp_fields(db)
        customer = User(email="designer@example.com", full_name="Test Designer")
        db.add(customer)
        db.commit()
        db.refresh(customer)
        design_repository = DesignRepository(db)
        design_repository.create_design(
            customer_id=customer.id,
            template_id=template.id,
            customization_values={
                "legend": "Existing valid design",
                "material": "vinyl",
                "width_cm": 30,
            },
        )
        service = build_validation_service(db)

        with pytest.raises(DesignValidationError):
            service.validate_customization(
                template_id=template.id,
                customization_values={
                    "legend": "Invalid design",
                    "material": "paper",
                    "width_cm": 30,
                },
            )

        assert design_count(db) == 1
        stored_design = design_repository.get_design_for_customer(1, customer.id)
        assert stored_design.customization_values == {
            "legend": "Existing valid design",
            "material": "vinyl",
            "width_cm": 30,
        }
    finally:
        db.close()


def test_design_validation_is_deterministic_across_repeated_calls():
    db = build_session()
    try:
        template = add_template_with_mvp_fields(db)
        service = build_validation_service(db)
        payload = {
            "material": "aluminum",
            "reflective": False,
            "legend": "Emergency exit",
            "width_cm": 30,
        }

        first_result = service.validate_customization(template.id, payload)
        second_result = service.validate_customization(template.id, payload)

        assert first_result == second_result
        assert list(first_result) == ["legend", "material", "width_cm", "reflective"]
        assert design_count(db) == 0
    finally:
        db.close()
