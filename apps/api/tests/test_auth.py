from datetime import UTC, datetime, timedelta
import asyncio

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthenticationError, AuthService


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


def test_auth_service_verifies_signed_access_token():
    auth_service = AuthService("test-token-secret")
    token = auth_service.create_access_token(user_id=42)

    subject = auth_service.verify_access_token(token)

    assert subject.user_id == 42


def test_auth_service_rejects_tampered_access_token():
    auth_service = AuthService("test-token-secret")
    token = auth_service.create_access_token(user_id=42)
    tampered_token = token.replace(".42.", ".43.")

    try:
        auth_service.verify_access_token(tampered_token)
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Expected tampered token to be rejected")


def test_auth_service_rejects_expired_access_token():
    auth_service = AuthService("test-token-secret")
    token = auth_service.create_access_token(
        user_id=42,
        expires_delta=timedelta(seconds=-1),
    )

    try:
        auth_service.verify_access_token(token)
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Expected expired token to be rejected")


def test_user_repository_gets_user_by_id():
    db = build_session()
    try:
        db.add(User(email="ada@example.com", full_name="Ada Lovelace"))
        db.commit()

        repository = UserRepository(db)

        user = repository.get_user_by_id(1)
        missing_user = repository.get_user_by_id(999)

        assert user is not None
        assert user.email == "ada@example.com"
        assert missing_user is None
    finally:
        db.close()


def test_get_current_user_endpoint_rejects_missing_credentials(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")

    async def get_current_user_response():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/api/v1/auth/me")

    response = asyncio.run(get_current_user_response())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}


def test_get_current_user_endpoint_rejects_invalid_credentials(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")

    async def get_current_user_response():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer invalid-token"},
            )

    response = asyncio.run(get_current_user_response())

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}


def test_get_current_user_endpoint_returns_authenticated_user(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    try:
        db.add_all(
            [
                User(email="ada@example.com", full_name="Ada Lovelace"),
                User(email="grace@example.com", full_name="Grace Hopper"),
            ]
        )
        db.commit()

        token = AuthService(settings.AUTH_TOKEN_SECRET).create_access_token(user_id=1)

        async def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        async def get_current_user_response():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(
                    "/api/v1/auth/me?user_id=2&role=admin&is_admin=true",
                    headers={"Authorization": f"Bearer {token}"},
                )

        response = asyncio.run(get_current_user_response())

        assert response.status_code == 200
        assert response.json()["id"] == 1
        assert response.json()["email"] == "ada@example.com"
        assert response.json()["full_name"] == "Ada Lovelace"
        assert response.json()["is_active"] is True
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_current_user_endpoint_rejects_inactive_user(monkeypatch):
    monkeypatch.setattr(settings, "AUTH_TOKEN_SECRET", "test-token-secret")
    db = build_session()
    try:
        db.add(User(email="inactive@example.com", is_active=False))
        db.commit()

        token = AuthService(settings.AUTH_TOKEN_SECRET).create_access_token(user_id=1)

        async def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db

        async def get_current_user_response():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": f"Bearer {token}"},
                )

        response = asyncio.run(get_current_user_response())

        assert response.status_code == 401
        assert response.json() == {"detail": "Invalid authentication credentials"}
    finally:
        app.dependency_overrides.clear()
        db.close()


def test_get_current_user_dependency_can_be_overridden_for_endpoint_tests():
    test_user = User(
        id=7,
        email="override@example.com",
        full_name="Override User",
        is_active=True,
        created_at=datetime(2026, 4, 29, tzinfo=UTC),
        updated_at=datetime(2026, 4, 29, tzinfo=UTC),
    )

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_current_user] = override_get_current_user

    try:

        async def get_current_user_response():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.get("/api/v1/auth/me")

        response = asyncio.run(get_current_user_response())

        assert response.status_code == 200
        assert response.json()["id"] == 7
        assert response.json()["email"] == "override@example.com"
    finally:
        app.dependency_overrides.clear()


def test_get_current_user_endpoint_is_documented_in_openapi():
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
    operation = schema["paths"]["/api/v1/auth/me"]["get"]
    assert operation["summary"] == "Get current user"
    assert "200" in operation["responses"]
