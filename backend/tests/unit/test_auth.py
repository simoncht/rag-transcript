import uuid

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.core import auth as auth_module
from app.core.auth import ClerkJWTVerifier, clerk_verifier
from app.core.config import settings
from app.models import User


class FakeQuery:
    """Minimal query stub to evaluate simple equality filters."""

    def __init__(self, session, model):
        self.session = session
        self.model = model
        self.conditions = []

    def filter(self, *conditions):
        self.conditions = conditions
        return self

    def _matches(self, obj):
        if not self.conditions:
            return True

        for cond in self.conditions:
            try:
                left_key = cond.left.key if hasattr(cond.left, "key") else cond.left.name
                right_val = getattr(cond.right, "value", None)
            except Exception:
                continue

            if getattr(obj, left_key, None) != right_val:
                return False
        return True

    def first(self):
        for obj in self.session._store:
            if isinstance(obj, self.model) and self._matches(obj):
                return obj
        return None


class FakeSession:
    """Minimal session stub for get_current_user tests."""

    def __init__(self, items=None):
        self._store = items or []
        self.committed = False

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self._store.append(obj)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        # No-op for stub
        return obj

    def close(self):
        return None


def test_clerk_verifier_relaxed_mode_returns_unverified_claims(monkeypatch):
    original_flag = settings.clerk_jwt_verification
    settings.clerk_jwt_verification = False

    try:
        token = "dummy-token"

        monkeypatch.setattr(
            jwt,
            "get_unverified_header",
            lambda t: {"kid": "test_kid"},
        )
        monkeypatch.setattr(
            jwt,
            "get_unverified_claims",
            lambda t: {"sub": "user_123", "iss": "https://example-issuer"},
        )

        verifier = ClerkJWTVerifier()
        claims = verifier.verify_and_decode(token)

        assert claims["sub"] == "user_123"
        assert claims["iss"] == "https://example-issuer"
    finally:
        settings.clerk_jwt_verification = original_flag


def test_clerk_verifier_strict_mode_uses_jwks_and_decode(monkeypatch):
    original_flag = settings.clerk_jwt_verification
    settings.clerk_jwt_verification = True

    try:
        token = "dummy-token"

        def fake_unverified_header(t):
            assert t == token
            return {"kid": "kid_1"}

        def fake_unverified_claims(t):
            assert t == token
            return {"sub": "user_abc", "iss": "https://issuer.example"}

        monkeypatch.setattr(jwt, "get_unverified_header", fake_unverified_header)
        monkeypatch.setattr(jwt, "get_unverified_claims", fake_unverified_claims)

        # Stub JWKS fetch
        jwks_payload = {"keys": [{"kid": "kid_1", "kty": "RSA"}]}
        monkeypatch.setattr(
            ClerkJWTVerifier,
            "_get_jwks",
            staticmethod(lambda issuer: jwks_payload),
        )

        decoded_payload = {"sub": "user_abc", "iss": "https://issuer.example"}

        def fake_decode(token_arg, key, **kwargs):
            assert token_arg == token
            assert key == {"kid": "kid_1", "kty": "RSA"}
            # issuer should either be explicit or match token issuer
            assert kwargs["issuer"] in (
                settings.clerk_issuer or "https://issuer.example",
            )
            return decoded_payload

        monkeypatch.setattr(jwt, "decode", fake_decode)

        verifier = ClerkJWTVerifier()
        claims = verifier.verify_and_decode(token)

        assert claims == decoded_payload
    finally:
        settings.clerk_jwt_verification = original_flag


def test_extract_email_variants():
    assert auth_module._extract_email({"email": "a@example.com"}) == "a@example.com"
    assert (
        auth_module._extract_email({"primary_email_address": "b@example.com"}) == "b@example.com"
    )
    assert (
        auth_module._extract_email(
            {"email_addresses": [{"email_address": "c@example.com"}]}
        )
        == "c@example.com"
    )
    assert auth_module._extract_email({"email_addresses": ["d@example.com"]}) == "d@example.com"


def test_get_current_user_creates_user_when_missing(monkeypatch):
    claims = {"sub": "user_sub_1", "email": "new@example.com", "name": "New User"}
    monkeypatch.setattr(auth_module.clerk_verifier, "verify_and_decode", lambda token: claims)

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="fake-token")
    db = FakeSession()

    user = auth_module.get_current_user(credentials=creds, db=db)

    assert user.clerk_user_id == "user_sub_1"
    assert user.email == "new@example.com"
    assert db.committed is True
    assert any(u.clerk_user_id == "user_sub_1" for u in db._store)


def test_get_current_user_reuses_existing_user(monkeypatch):
    claims = {"sub": "user_sub_existing", "email": "existing@example.com"}
    monkeypatch.setattr(auth_module.clerk_verifier, "verify_and_decode", lambda token: claims)

    existing = User(
        id=uuid.uuid4(),
        clerk_user_id="user_sub_existing",
        email="existing@example.com",
        is_active=True,
    )
    db = FakeSession(items=[existing])
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    user = auth_module.get_current_user(credentials=creds, db=db)

    assert user is existing
    assert db.committed is False  # No new user created


def test_get_current_user_rejects_inactive_user(monkeypatch):
    claims = {"sub": "user_inactive", "email": "inactive@example.com"}
    monkeypatch.setattr(auth_module.clerk_verifier, "verify_and_decode", lambda token: claims)

    inactive = User(
        id=uuid.uuid4(),
        clerk_user_id="user_inactive",
        email="inactive@example.com",
        is_active=False,
    )
    db = FakeSession(items=[inactive])
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="token")

    with pytest.raises(HTTPException) as excinfo:
        auth_module.get_current_user(credentials=creds, db=db)

    assert excinfo.value.status_code == 403


def test_get_current_user_requires_bearer_scheme(monkeypatch):
    claims = {"sub": "user_wrong_scheme"}
    monkeypatch.setattr(auth_module.clerk_verifier, "verify_and_decode", lambda token: claims)

    db = FakeSession()
    creds = HTTPAuthorizationCredentials(scheme="Basic", credentials="token")

    with pytest.raises(HTTPException) as excinfo:
        auth_module.get_current_user(credentials=creds, db=db)

    assert excinfo.value.status_code == 401


def test_get_current_user_requires_credentials():
    db = FakeSession()

    with pytest.raises(HTTPException) as excinfo:
        auth_module.get_current_user(credentials=None, db=db)

    assert excinfo.value.status_code == 401
