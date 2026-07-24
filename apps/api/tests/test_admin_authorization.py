import asyncio

import httpx
from app.api.dependencies import require_admin_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.repositories.audit_log_repository import AuditLogRepository
from app.services.audit_log_service import AuditLogService
from app.services.auth_service import AuthService
from fastapi import Depends, FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def build_session():
    """Create an isolated in-memory database session for admin tests.

    Returns:
        SQLAlchemy session bound to an in-memory SQLite database.

    Side effects:
        Creates all model tables in the in-memory database.
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


def build_admin_test_app() -> FastAPI:
    """Create a test-only FastAPI app with an admin-protected route.

    Returns:
        FastAPI app exposing a representative admin-protected behavior.

    Side effects:
        Registers a route on the returned test app only.
    """
    test_app = FastAPI()

    @test_app.get("/admin/probe")
    async def admin_probe(admin_user: User = Depends(require_admin_user)):
        """Return the authenticated admin user's identifier.

        Args:
            admin_user: User resolved by the reusable admin dependency.

        Returns:
            Minimal response proving the admin dependency allowed access.

        Side effects:
            None.
        """
        return {"id": admin_user.id}

    return test_app


def test_admin_dependency_rejects_unauthenticated_requests(monkeypatch):
    """Verify admin-protected behavior rejects missing credentials.

    Args:
        monkeypatch: Pytest fixture used to isolate authentication settings.

    Returns:
        None.

    Side effects:
        Temporarily overrides test app dependencies and settings.
    """
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    test_app = build_admin_test_app()

    async def override_get_db():
        try:
            yield db
        finally:
            pass

    test_app.dependency_overrides[get_db] = override_get_db

    try:

        async def get_admin_response():
            transport = httpx.ASGITransport(app=test_app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/admin/probe")

        response = asyncio.run(get_admin_response())

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authentication credentials"}
    finally:
        test_app.dependency_overrides.clear()
        db.close()


def test_admin_dependency_rejects_authenticated_non_admin(monkeypatch):
    """Verify admin checks use the authenticated database user role.

    Args:
        monkeypatch: Pytest fixture used to isolate authentication settings.

    Returns:
        None.

    Side effects:
        Inserts a non-admin user into the test database.
    """
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    test_app = build_admin_test_app()

    try:
        db.add(User(email="user@example.com", role=UserRole.USER))
        db.commit()

        token = AuthService(settings.AUTH_TOKEN_SECRET).create_access_token(user_id=1)

        async def override_get_db():
            try:
                yield db
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        async def get_admin_response():
            transport = httpx.ASGITransport(app=test_app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(
                    "/admin/probe?role=admin&is_admin=true&user_id=1",
                    headers={"Authorization": f"Bearer {token}"},
                )

        response = asyncio.run(get_admin_response())

        assert response.status_code == 403
        assert response.json() == {"detail": "Admin privileges are required"}
    finally:
        test_app.dependency_overrides.clear()
        db.close()


def test_admin_dependency_allows_authenticated_admin(monkeypatch):
    """Verify admin users resolved from the database pass the guard.

    Args:
        monkeypatch: Pytest fixture used to isolate authentication settings.

    Returns:
        None.

    Side effects:
        Inserts an admin user into the test database.
    """
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    test_app = build_admin_test_app()

    try:
        db.add(User(email="admin@example.com", role=UserRole.ADMIN))
        db.commit()

        token = AuthService(settings.AUTH_TOKEN_SECRET).create_access_token(user_id=1)

        async def override_get_db():
            try:
                yield db
            finally:
                pass

        test_app.dependency_overrides[get_db] = override_get_db

        async def get_admin_response():
            transport = httpx.ASGITransport(app=test_app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(
                    "/admin/probe",
                    headers={"Authorization": f"Bearer {token}"},
                )

        response = asyncio.run(get_admin_response())

        assert response.status_code == 200
        assert response.json() == {"id": 1}
    finally:
        test_app.dependency_overrides.clear()
        db.close()


def test_audit_log_service_records_representative_admin_action():
    """Verify audit logs capture admin context and redact sensitive details.

    Returns:
        None.

    Side effects:
        Inserts an admin user and audit log record into the test database.
    """
    db = build_session()

    try:
        admin_user = User(email="admin@example.com", role=UserRole.ADMIN)
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        audit_log_service = AuditLogService(AuditLogRepository(db))
        audit_log = audit_log_service.record_admin_action(
            actor=admin_user,
            action="product.update",
            resource_type="product",
            resource_id=123,
            event_details={
                "changed_fields": ["name", "base_price"],
                "reason": "catalog correction",
                "password": "do-not-store",
                "nested": {"api_token": "do-not-store"},
                "full_environment": {"AUTH_TOKEN_SECRET": "do-not-store"},
            },
        )
        db.commit()

        stored_audit_log = db.execute(select(AuditLog)).scalar_one()

        assert audit_log.id == stored_audit_log.id
        assert stored_audit_log.actor_user_id == admin_user.id
        assert stored_audit_log.action == "product.update"
        assert stored_audit_log.resource_type == "product"
        assert stored_audit_log.resource_id == "123"
        assert stored_audit_log.event_details["changed_fields"] == [
            "name",
            "base_price",
        ]
        assert stored_audit_log.event_details["password"] == "[REDACTED]"
        assert stored_audit_log.event_details["nested"]["api_token"] == "[REDACTED]"
        assert stored_audit_log.event_details["full_environment"] == "[REDACTED]"
    finally:
        db.close()


def test_audit_log_service_redacts_expanded_sensitive_key_names():
    """Verify expanded sensitive audit keys are redacted recursively.

    Returns:
        None.

    Side effects:
        Inserts an admin user and audit log record into the test database.
    """
    db = build_session()

    try:
        admin_user = User(email="admin@example.com", role=UserRole.ADMIN)
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        audit_log_service = AuditLogService(AuditLogRepository(db))
        audit_log_service.record_admin_action(
            actor=admin_user,
            action="security.redaction_check",
            resource_type="audit_log",
            event_details={
                "jwt": "do-not-store",
                "refresh_token": "do-not-store",
                "access_token": "do-not-store",
                "api_key": "do-not-store",
                "private_key": "do-not-store",
                "wompi_integrity_secret": "do-not-store",
                "signature_preimage": "do-not-store",
                "signature:integrity": "do-not-store",
                "signed_checkout_url": "do-not-store",
                "handoff_url": "do-not-store",
                "nested": [{"refresh_token": "do-not-store"}],
                "safe_note": "keep this",
            },
        )
        db.commit()

        stored_audit_log = db.execute(select(AuditLog)).scalar_one()

        assert stored_audit_log.event_details["jwt"] == "[REDACTED]"
        assert stored_audit_log.event_details["refresh_token"] == "[REDACTED]"
        assert stored_audit_log.event_details["access_token"] == "[REDACTED]"
        assert stored_audit_log.event_details["api_key"] == "[REDACTED]"
        assert stored_audit_log.event_details["private_key"] == "[REDACTED]"
        assert stored_audit_log.event_details["wompi_integrity_secret"] == "[REDACTED]"
        assert stored_audit_log.event_details["signature_preimage"] == "[REDACTED]"
        assert stored_audit_log.event_details["signature:integrity"] == "[REDACTED]"
        assert stored_audit_log.event_details["signed_checkout_url"] == "[REDACTED]"
        assert stored_audit_log.event_details["handoff_url"] == "[REDACTED]"
        assert (
            stored_audit_log.event_details["nested"][0]["refresh_token"] == "[REDACTED]"
        )
        assert stored_audit_log.event_details["safe_note"] == "keep this"
    finally:
        db.close()


def test_audit_log_service_redacts_documented_sensitive_value_patterns():
    """Verify deterministic value-based redaction covers documented patterns.

    Returns:
        None.

    Side effects:
        Inserts an admin user and audit log record into the test database.
    """
    db = build_session()

    try:
        admin_user = User(email="admin@example.com", role=UserRole.ADMIN)
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)

        jwt_like_value = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
        pem_private_key_value = (
            "-----BEGIN PRIVATE KEY-----\ndo-not-store\n-----END PRIVATE KEY-----"
        )

        audit_log_service = AuditLogService(AuditLogRepository(db))
        audit_log_service.record_admin_action(
            actor=admin_user,
            action="security.value_redaction_check",
            resource_type="audit_log",
            event_details={
                "provider_reference": "local-order-1",
                "signed_payload": jwt_like_value,
                "diagnostic_block": pem_private_key_value,
                "ordinary_dotted_value": "catalog.product.created",
            },
        )
        db.commit()

        stored_audit_log = db.execute(select(AuditLog)).scalar_one()

        assert stored_audit_log.event_details["provider_reference"] == "local-order-1"
        assert stored_audit_log.event_details["signed_payload"] == "[REDACTED]"
        assert stored_audit_log.event_details["diagnostic_block"] == "[REDACTED]"
        assert (
            stored_audit_log.event_details["ordinary_dotted_value"]
            == "catalog.product.created"
        )
    finally:
        db.close()
