import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import auth as auth_routes
from app.core.nextauth import get_current_user
from app.models import User


def _fake_user():
    return User(
        id=uuid.uuid4(),
        email="authping@example.com",
        is_active=True,
    )


def create_test_app():
    app = FastAPI()
    app.include_router(auth_routes.router, prefix="/api/v1/auth")
    app.dependency_overrides[get_current_user] = _fake_user
    return app


def test_auth_ping_returns_user_info():
    app = create_test_app()
    client = TestClient(app)

    resp = client.get("/api/v1/auth/ping")
    assert resp.status_code == 200

    data = resp.json()
    assert data["status"] == "ok"
    assert data["email"] == "authping@example.com"
    assert data["user_id"]
