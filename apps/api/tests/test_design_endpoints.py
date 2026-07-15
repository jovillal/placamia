import asyncio

import httpx
import pytest
from app.api.dependencies import get_current_user
from app.core.database import Base, get_db
from app.main import app
from app.models.design import Design
from app.models.template import Template
from app.models.template_field import TemplateField
from app.models.user import User
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Build an isolated database session for Design endpoint tests."""
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
    """Persist one authenticated customer."""
    user = User(email=email, full_name="Test Designer")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def seed_template(db, *, is_active: bool = True) -> Template:
    """Persist one Template with the supported MVP field set."""
    template = Template(
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


def valid_payload(template_id: int) -> dict[str, object]:
    """Return one valid Design creation request."""
    return {
        "template_id": template_id,
        "customization_values": {
            "legend": "Emergency exit",
            "material": "vinyl",
            "width_cm": 30,
            "reflective": True,
        },
    }


def design_snapshot(db) -> list[tuple[object, ...]]:
    """Return persisted Design state for no-mutation assertions."""
    return db.execute(select(Design.__table__).order_by(Design.id)).all()


def track_commits(db) -> dict[str, int]:
    """Count commits performed after endpoint test setup is complete."""
    commit_tracker = {"count": 0}
    original_commit = db.commit

    def tracked_commit() -> None:
        commit_tracker["count"] += 1
        original_commit()

    db.commit = tracked_commit
    return commit_tracker


async def post_design(payload: dict[str, object]):
    """Call the authenticated Design creation endpoint."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.post("/api/v1/designs", json=payload)


async def get_design(design_id: int):
    """Call the authenticated Design retrieval endpoint."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        return await client.get(f"/api/v1/designs/{design_id}")


def configure_design_endpoint_test(
    db,
    current_user: User | None,
) -> None:
    """Install database and optional authentication dependency overrides."""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    if current_user is not None:

        async def override_get_current_user():
            return current_user

        app.dependency_overrides[get_current_user] = override_get_current_user


def test_create_design_endpoint_persists_validated_owner_design():
    db = build_session()
    try:
        customer = seed_user(db)
        template = seed_template(db)
        configure_design_endpoint_test(db, customer)
        commit_tracker = track_commits(db)

        response = asyncio.run(post_design(valid_payload(template.id)))

        assert response.status_code == 201
        assert response.json() == {
            "id": 1,
            "template_id": template.id,
            "customization_values": {
                "legend": "Emergency exit",
                "material": "vinyl",
                "width_cm": 30,
                "reflective": True,
            },
        }
        design = db.scalar(select(Design))
        assert design.customer_id == customer.id
        assert design.template_id == template.id
        assert design.customization_values == response.json()["customization_values"]
        assert commit_tracker["count"] == 1
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_create_design_endpoint_rejects_unauthenticated_request_without_mutation():
    db = build_session()
    try:
        template = seed_template(db)
        configure_design_endpoint_test(db, None)
        persistence_before = design_snapshot(db)
        commit_tracker = track_commits(db)

        response = asyncio.run(post_design(valid_payload(template.id)))

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authentication credentials"}
        assert design_snapshot(db) == persistence_before
        assert commit_tracker["count"] == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_create_design_endpoint_hides_unknown_and_inactive_templates_identically():
    db = build_session()
    try:
        customer = seed_user(db)
        inactive_template = seed_template(db, is_active=False)
        configure_design_endpoint_test(db, customer)
        persistence_before = design_snapshot(db)
        commit_tracker = track_commits(db)

        inactive_response = asyncio.run(
            post_design(valid_payload(inactive_template.id))
        )
        unknown_response = asyncio.run(post_design(valid_payload(999)))

        assert inactive_response.status_code == 404
        assert unknown_response.status_code == 404
        assert inactive_response.json() == {"detail": "Template not found"}
        assert unknown_response.json() == inactive_response.json()
        assert design_snapshot(db) == persistence_before
        assert commit_tracker["count"] == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("customization_values", "code", "message"),
    [
        (
            {"legend": "Emergency exit", "width_cm": 30},
            "missing_required_field",
            "Customization is missing required TemplateFields.",
        ),
        (
            {
                "legend": "Emergency exit",
                "material": "vinyl",
                "width_cm": 30,
                "frontend_key": "untrusted",
            },
            "unknown_template_field",
            "Customization includes fields not defined for the Template.",
        ),
        (
            {
                "legend": "Emergency exit",
                "material": "vinyl",
                "width_cm": "30",
            },
            "invalid_value_type",
            "Number fields require numeric values.",
        ),
        (
            {
                "legend": "Emergency exit",
                "material": "paper",
                "width_cm": 30,
            },
            "invalid_select_value",
            "Select value is not allowed.",
        ),
    ],
)
def test_create_design_endpoint_returns_customer_safe_customization_errors(
    customization_values,
    code,
    message,
):
    db = build_session()
    try:
        customer = seed_user(db)
        template = seed_template(db)
        configure_design_endpoint_test(db, customer)
        persistence_before = design_snapshot(db)
        commit_tracker = track_commits(db)

        response = asyncio.run(
            post_design(
                {
                    "template_id": template.id,
                    "customization_values": customization_values,
                }
            )
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": {
                "code": code,
                "message": message,
            }
        }
        assert design_snapshot(db) == persistence_before
        assert not db.new
        assert not db.dirty
        assert not db.deleted
        assert commit_tracker["count"] == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("fields", "customization_values"),
    [
        (
            [
                {
                    "field_name": "color",
                    "field_type": "color",
                    "allowed_values": None,
                }
            ],
            {"color": "red"},
        ),
        (
            [
                {
                    "field_name": "legend",
                    "field_type": "text",
                    "allowed_values": None,
                },
                {
                    "field_name": "legend",
                    "field_type": "text",
                    "allowed_values": None,
                },
            ],
            {"legend": "Emergency exit"},
        ),
        (
            [
                {
                    "field_name": "legend",
                    "field_type": "text",
                    "allowed_values": ["not-valid-for-text"],
                }
            ],
            {"legend": "Emergency exit"},
        ),
    ],
)
def test_create_design_endpoint_hides_malformed_backend_configuration(
    fields,
    customization_values,
):
    db = build_session()
    try:
        customer = seed_user(db)
        template = Template(name="Malformed template", description=None)
        db.add_all(
            [
                TemplateField(
                    template=template,
                    field_name=field["field_name"],
                    field_type=field["field_type"],
                    is_required=True,
                    allowed_values=field["allowed_values"],
                    display_order=index,
                )
                for index, field in enumerate(fields, start=1)
            ]
        )
        db.commit()
        db.refresh(template)
        configure_design_endpoint_test(db, customer)
        persistence_before = design_snapshot(db)
        commit_tracker = track_commits(db)

        response = asyncio.run(
            post_design(
                {
                    "template_id": template.id,
                    "customization_values": customization_values,
                }
            )
        )

        assert response.status_code == 409
        assert response.json() == {
            "detail": {
                "code": "design_configuration_unavailable",
                "message": "Design configuration is unavailable.",
            }
        }
        assert design_snapshot(db) == persistence_before
        assert commit_tracker["count"] == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("customer_id", 999),
        ("user_id", 999),
        ("owner_id", 999),
        ("role", "admin"),
        ("template_fields", []),
        ("frontend_price", "1.00"),
        ("provider_id", "forged-provider"),
        ("is_active", True),
        ("created_at", "2026-07-15T00:00:00Z"),
        ("id", 42),
    ],
)
def test_create_design_endpoint_forbids_authoritative_extra_fields(
    field_name,
    field_value,
):
    db = build_session()
    try:
        customer = seed_user(db)
        template = seed_template(db)
        configure_design_endpoint_test(db, customer)
        payload = valid_payload(template.id)
        payload[field_name] = field_value
        persistence_before = design_snapshot(db)
        commit_tracker = track_commits(db)

        response = asyncio.run(post_design(payload))

        assert response.status_code == 422
        assert design_snapshot(db) == persistence_before
        assert commit_tracker["count"] == 0
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_design_endpoint_returns_exact_owned_read_only_resource():
    db = build_session()
    try:
        owner = seed_user(db)
        template = seed_template(db)
        design = Design(
            customer=owner,
            template=template,
            customization_values={"legend": "Emergency exit"},
        )
        db.add(design)
        db.commit()
        db.refresh(design)
        configure_design_endpoint_test(db, owner)
        persistence_before = design_snapshot(db)

        response = asyncio.run(get_design(design.id))

        assert response.status_code == 200
        assert response.json() == {
            "id": design.id,
            "template_id": template.id,
            "customization_values": {"legend": "Emergency exit"},
        }
        assert design_snapshot(db) == persistence_before
        assert not db.new
        assert not db.dirty
        assert not db.deleted
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_design_endpoint_rejects_unauthenticated_request():
    db = build_session()
    try:
        owner = seed_user(db)
        template = seed_template(db)
        design = Design(
            customer=owner,
            template=template,
            customization_values={"legend": "Emergency exit"},
        )
        db.add(design)
        db.commit()
        configure_design_endpoint_test(db, None)

        response = asyncio.run(get_design(design.id))

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authentication credentials"}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_design_endpoint_hides_cross_user_and_unknown_designs_identically():
    db = build_session()
    try:
        owner = seed_user(db, "owner@example.com")
        other_customer = seed_user(db, "other@example.com")
        template = seed_template(db)
        design = Design(
            customer=owner,
            template=template,
            customization_values={"legend": "Emergency exit"},
        )
        db.add(design)
        db.commit()
        db.refresh(design)
        configure_design_endpoint_test(db, other_customer)
        persistence_before = design_snapshot(db)

        cross_user_response = asyncio.run(get_design(design.id))
        unknown_response = asyncio.run(get_design(999))

        assert cross_user_response.status_code == 404
        assert unknown_response.status_code == 404
        assert cross_user_response.json() == {"detail": "Design not found"}
        assert unknown_response.json() == cross_user_response.json()
        assert design_snapshot(db) == persistence_before
    finally:
        app.dependency_overrides.clear()
        db.close()
